# -*- coding: utf-8 -*-
# all the imports
import datetime
from csv import writer as csv_writer
import json
import sqlite3
from flask import Flask, Response, request, g, render_template, send_from_directory, redirect
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text
from contextlib import closing
from random import choice
import re
import time

# configuration
DATABASE = 'crs_small.sqlite'
# DATABASE = 'crs_complete.sqlite'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'dev'
REGIONFILTER = [998, 889, 798, 789, 689, 679, 619, 589, 498, 489, 389, 380, 298, 289, 258, 189, 89, 88]

app = Flask(__name__)
app.config.from_object(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root@localhost:3306/crs'

# app.config['FREEZER_RELATIVE_URLS'] = True
db = SQLAlchemy(app)

# Scss(app, static_dir='static', asset_dir='assets')


def query_db(query):
    q = db.engine.execute(text(query)).fetchall()
    return q


def query_db_one(query):
    q = db.engine.execute(text(query)).fetchone()
    return q[0]


def tremapCalc(t):
    t['show'] = "true"
    if t['treearea'] <= 10:
        t['color'] = "#84aaac"
        t['show'] = "false"
    elif t['treearea'] > 10 and t['treearea'] < 35:
        t['color'] = "#5a8d8f"
    elif t['treearea'] > 35 and t['treearea'] < 55:
        t['color'] = "#2f7073"
    elif t['treearea'] > 55:
        t['color'] = "#055356"
    return t


def sitemap(link):
    url = "http://www.openaiddata.org/"
    part = "<url><loc>" + url + link + "</loc><lastmod>" + datetime.datetime.now().isoformat() + "</lastmod></url>\n"
    return part


def filter_region(code):
    if code not in REGIONFILTER:
            return True


def future_years(years, country):
    year = {'jahr': g.year + 1, 'recipientcode': country}
    years.append(year)
    year2 = {'jahr': g.year + 2, 'recipientcode': country}
    years.append(year2)
    return years


def year_check(year_list, year):
    if year in year_list:
            return True
    else:
            return False


@app.template_filter()
def number_trunc(float):
    return "%.*f" % (0, float)


@app.template_filter()
def regex_replace(s, find, replace):
    return re.sub(find, replace, s)


@app.template_filter()
def number_format(value, tsep=',', dsep='.'):
    s = unicode(value)
    cnt = 0
    numchars = dsep + '0123456789'
    ls = len(s)
    while cnt < ls and s[cnt] not in numchars:
            cnt += 1
    lhs = s[:cnt]
    s = s[cnt:]
    if not dsep:
            cnt = -1
    else:
            cnt = s.rfind(dsep)
    if cnt > 0:
            rhs = dsep + s[cnt + 1:]
            s = s[:cnt]
    else:
            rhs = ''
    splt = ''
    while s != '':
            splt = s[-3:] + tsep + splt
            s = s[:-3]
    return lhs + splt[:-1] + rhs


@app.before_request
def before_request():
    g.year = 2013
    g.start_year = 2000
    g.rendered = (time.strftime("%d/%m/%Y"))


@app.teardown_request
def teardown_request(exception):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db'):
            g.db.close()


@app.route('/')
def show_start():

    all_activities = query_db_one('select count(*) as total from crs where usd_commitment > 0')

    gesamt = []
    for row in query_db('SELECT Year, round(sum(usd_disbursement  * 1000000)) as total_sum from crs where Year between 2000 and ' + str(g.year) + ' group by Year'):
            d = dict(row.items())
            for k in query_db('SELECT Year, round(sum(usd_disbursement  * 1000000)) as red_sum from crs where Year between 2000 and ' + str(g.year) + '  group by Year'):
                    dic = dict(k.items())
                    d['total'] = dic['red_sum']
                    gesamt.append(d)

    total = query_db_one('SELECT round(sum(usd_disbursement  * 1000000),2) as total, crsid, sectorname from crs order by total desc')

    entries = []
    for row in query_db('SELECT round(sum(usd_disbursement  * 1000000),2) as main_value, crsid, sectorname, sectorcode from crs where usd_commitment > 0 and sectorcode != 0 group by sectorname order by main_value desc'):
            d = dict(row.items())
            d['treearea'] = (d['main_value'] / total) * 170
            d = tremapCalc(d)
            entries.append(d)

    return render_template('start.html', all_activities=all_activities, entries=entries, gesamt=gesamt)
    # return str(gesamt)


@app.route('/recipient_countries/')
def show_countries():
    info = query_db('SELECT crs_country as land, crs_code as recipientcode from countries where crs_country != "" and crs_code != 858')

    return render_template('recipient_countries.html', info=info)


@app.route('/donors/')
def show_donors():
    info = query_db('SELECT donorname, donorcode from crs where donorcode not in (990, 811, 976, 988, 901, 966, 923) group by donorname')

    return render_template('donors.html', info=info)


@app.route('/recipient_country/<country>/<year>/')
def show_recipient_year(country, year):

    sitemap_file = open('sitemap.xml', 'a')
    link = 'recipient_country/' + country + '/' + year
    input = sitemap(link)
    sitemap_file.write(input)
    sitemap_file.close()

    year = int(year)

    position = query_db('SELECT id from crs_donortop where recipientcode = {0}'.format(country))

    topsector = query_db('select sum(usd_disbursement * 1000000) as total, sectorcode, sectorname from crs where recipientcode = {0} group by sectorname order by total desc limit 5'.format(country))

    result_top = len(topsector)
    sectorYearPrep = "SELECT Year, "

    i = 1
    for s in topsector:
        q = "SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector" % (s['sectorcode'])
        sectorYearPrep = sectorYearPrep + q + str(i)
        if i < result_top:
            sectorYearPrep = sectorYearPrep + ","
        i += 1

    sectorYearPrep = sectorYearPrep + " from crs where recipientcode = %s group by Year" % (country)

    sectoryears = query_db(sectorYearPrep)

    info = []
    for row in query_db('SELECT count(crsid) as total_activities, recipientname as land, recipientcode, round(sum(usd_commitment * 1000000)) as total_sum, round(sum(usd_disbursement * 1000000)) as disbursement from crs where Year between 2000 and {0} and usd_commitment > 0 and recipientcode = {1}'.format(str(g.year), country)):
        d = dict(row.items())
        d['jahr'] = year
        info.append(d)

    if filter_region(int(country)):
        wb_iso = query_db_one('SELECT wb_iso from countries where crs_code = {1}'.format(year, country))
    else:
        wb_iso = "XXX"

    iff = []
    for row in query_db('SELECT year, country, (value * 1000000) as value from iff where country = (select iff_country from countries where crs_code = {0})'.format(country)):
        d = dict(row.items())
        iff.append(d)

    if year > g.year:
        totalYear = query_db_one("select sum(value) as main_value from iati where recipient_country = (select iati_country from countries where crs_code = {1}) and YEAR(transaction_date) = {0}".format(year, country))
    else:
        totalYear = query_db_one('SELECT round(sum(usd_disbursement * 1000000)) as total from crs where usd_commitment > 0 and Year = {0} and recipientcode = {1}'.format(year, country))
    totalYear = totalYear or 1

    iati_entries = []
    for row in query_db("select name as sectorname, count(*) as transactions, id, sum(value) as main_value from iati join iati_sectors on code = sector_code where recipient_country = (select iati_country from countries where crs_code = {0}) and YEAR(transaction_date) = {1} and sector != '' and value > 0 and transaction_type not in ('Commitments', 'COMMITMENT', 'Commitments') group by sector_code order by main_value DESC limit 30".format(country, year)):
        d = dict(row.items())
        if year > g.year:
            d['treearea'] = (d['main_value'] / totalYear) * 100
            d = tremapCalc(d)
        iati_entries.append(d)

    if year <= g.year:
        crs_entries = []
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000)) as main_value, crsid as id, sectorname, sectorcode, recipientcode, count(sectorname) as activities, Year from crs where recipientcode = {0} and Year = {1} and usd_commitment > 0 group by sectorname order by main_value desc'.format(country, year)):
            d = dict(row.items())
            d['treearea'] = (d['main_value'] / totalYear) * 100
            d = tremapCalc(d)
            crs_entries.append(d)
    else:
        crs_entries = iati_entries

    disbYears = []
    years = []
    for row in query_db('select Year as jahr, recipientcode from crs where length(usd_disbursement) > 0 and usd_commitment > 0 and recipientcode = {0} and Year between 2000 and {1} group by Year'.format(country, str(g.year))):
        d = dict(row.items())
        years.append(d['jahr'])
        disbYears.append(d)

    # adds navigation with further and correct years
    disbYears = future_years(disbYears, country)
    years.append(int(g.year + 1))
    years.append(int(g.year + 2))
    previous_year = year_check(years, int(year) - 1)
    next_year = year_check(years, int(year) + 1)

    return render_template('recipient_country.html', totalYear=totalYear, iff=iff, crs_entries=crs_entries, info=info, wb_iso=wb_iso, position=position, disbYears=disbYears, iati_entries=iati_entries, topsector=topsector, sectoryears=sectoryears, previous_year=previous_year, next_year=next_year)


@app.route('/recipient_country/<country>/<year>/crs.csv')
def generate_large_csv(country, year):
    def generate():
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000)) as main_value, crsid as id, sectorname, sectorcode, recipientcode, count(sectorname) as activities, Year from crs where recipientcode = {0} and Year = {1} and usd_commitment > 0 group by sectorname order by main_value desc'.format(country, year)):
            for crs in row:
                yield ','.join(row[0]) + '\n'

    return Response(generate(), mimetype='text/csv')


@app.route('/donor/<donor>/<year>/')
def show_donor_year(donor, year):

        sitemap_file = open('sitemap.xml', 'a')
        link = 'donor/' + donor + '/' + year
        input = sitemap(link)
        sitemap_file.write(input)
        sitemap_file.close()

        topsector = query_db('select sum(usd_disbursement * 1000000) as total, sectorcode, sectorname from crs where donorcode = {0} group by sectorname order by total desc limit 5'.format(donor))

        result_top = len(topsector)
        sectorYearPrep = "SELECT Year, "

        i = 1
        for s in topsector:
            q = "SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector" % (s['sectorcode'])
            sectorYearPrep = sectorYearPrep + q + str(i)
            if i < result_top:
                    sectorYearPrep = sectorYearPrep + ","
            i += 1

        sectorYearPrep = sectorYearPrep + " from crs where donorcode = %s group by Year" % (donor)

        sectoryears = query_db(sectorYearPrep)

        info = []
        for row in query_db('SELECT count(crsid) as total_activities, donorname, donorcode, round(sum(usd_commitment * 1000000)) as total_sum, round(sum(usd_disbursement * 1000000)) as disbursement from crs where Year between 2000 and {0} and usd_commitment > 0 and donorcode = {1}'.format(str(g.year), donor)):
            d = dict(row.items())
            d['jahr'] = year
            info.append(d)

        totalYear = query_db_one('SELECT round(sum(usd_disbursement * 1000000)) as total from crs where usd_commitment > 0 and Year = {0} and donorcode = {1}'.format(year, donor))
        totalYear = totalYear or 1

        flows = []
        for row in query_db('SELECT Year, SUM(CASE WHEN flowcode = 11 THEN usd_disbursement * 1000000 ELSE 0 END) AS gg, SUM(CASE WHEN flowcode = 13 THEN usd_disbursement * 1000000 ELSE 0 END) AS ll from crs where donorcode = {0} group by Year'.format(donor)):
            d = dict(row.items())
            flows.append(d)

        recipient_countries = []
        for row in query_db('select round(sum(usd_disbursement * 1000000)) as main_value, recipientname, recipientcode, count(id) as activities from crs where donorcode = {0} and Year = {1} group by recipientname order by main_value desc limit 10'.format(donor, year)):
            d = dict(row.items())
            recipient_countries.append(d)

        crs_entries = []
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000)) as main_value, crsid, sectorname, sectorcode, recipientcode, count(sectorname) as activities, Year from crs where donorcode = {0} and Year = {1} and usd_commitment > 0 group by sectorname order by main_value desc'.format(donor, year)):
            d = dict(row.items())
            d['treearea'] = (d['main_value'] / totalYear) * 100
            d = tremapCalc(d)
            crs_entries.append(d)

        disbYears = []
        years = []
        for row in query_db('select Year as jahr, donorcode from crs where length(usd_disbursement) > 1 and donorcode = {0} and Year between 2000 and {1} group by Year'.format(donor, str(g.year))):
            d = dict(row.items())
            years.append(d['jahr'])
            disbYears.append(d)

        previous_year = year_check(years, int(year) - 1)
        next_year = year_check(years, int(year) + 1)

        return render_template('donor.html', totalYear=totalYear, crs_entries=crs_entries, info=info, disbYears=disbYears, topsector=topsector, sectoryears=sectoryears, flows=flows, previous_year=previous_year, next_year=next_year, recipient_countries=recipient_countries)


@app.route('/purpose/<country>/<sector>/<donor>/')
def show_sektor(country, sector, donor):

        sitemap_file = open('sitemap.xml', 'a')
        link = 'purpose/' + country + '/' + sector + '/' + donor
        input = sitemap(link)
        sitemap_file.write(input)
        sitemap_file.close()

        entries = []
        if donor == "top":
            for row in query_db('SELECT crsid, round(usd_disbursement * 1000000,2) as main_value, flowname, agencyname, donorname, id, sectorname, sectorcode, purposename, projecttitle, Year from crs where recipientcode = {0} and sectorcode = {1} and round(usd_disbursement * 1000000,2) > 0 order by main_value desc limit 100'.format(country, sector, str(g.year))):
                d = dict(row.items())
                entries.append(d)

        else:
            for row in query_db('SELECT crsid, round(usd_disbursement * 1000000,2) as main_value, flowname, donorname, agencyname, recipientname, id, sectorname, sectorcode, purposename, projecttitle, Year from crs where recipientcode = {0} and sectorcode = {1} and donorcode = {2} and round(usd_disbursement * 1000000,2) > 0 order by main_value desc'.format(country, sector, donor)):
                d = dict(row.items())
                entries.append(d)

        donors = query_db('select donorname, donorcode from crs where recipientcode = {0} and sectorcode = {1} and usd_disbursement * 1000000 > 1 group by donorname'.format(country, sector))

        activities = query_db('SELECT Year, sectorcode, sectorname, count(recipientcode) as total_activities from crs where Year between 2000 and {0} and recipientcode = {1} and sectorcode = {2} and usd_commitment > 0 group by Year'.format(str(g.year), country, sector))

        totalYear = []
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000)) as total, round(sum(usd_disbursement * 1000000)) as disb_total, recipientname as land, recipientcode, donorname, sectorname, sectorcode from crs where Year between 2000 and {0} and recipientcode = {1} and sectorcode = {2}'.format(str(g.year), country, sector)):
            d = dict(row.items())
            d['donorcode'] = donor
            totalYear.append(d)

        flows = []
        for row in query_db('SELECT Year, SUM(CASE WHEN flowcode = 11 THEN usd_disbursement * 1000000 ELSE 0 END) AS gg, SUM(CASE WHEN flowcode = 13 THEN usd_disbursement * 1000000 ELSE 0 END) AS ll from crs where recipientcode = {0} and sectorcode = {1} group by Year'.format(country, sector)):
            d = dict(row.items())
            flows.append(d)

        spitzenreiter = []
        for row in query_db('SELECT total, sectorname, land, activities from crs_sectortop where sectorcode = {0}'.format(sector)):
            d = dict(row.items())
            spitzenreiter.append(d)

        purposes = []
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, id, sectorname, purposename, donorname, sectorcode, Year from crs where recipientcode = {0} and sectorcode = {1} and Year between 2000 and {2} group by purposename order by Year desc'.format(country, sector, str(g.year))):
            d = dict(row.items())
            d['treearea'] = (d['main_value'] / totalYear[0]['total']) * 100
            d = tremapCalc(d)
            purposes.append(d)

        return render_template('recipient_purpose.html', donors=donors, purposes=purposes, entries=entries, flows=flows, activities=activities, totalYear=totalYear, spitzenreiter=spitzenreiter)


@app.route('/sectors/<year>/')
def show_schwerpunkte(year):
        var = {'year': year}

        sitemap_file = open('sitemap.xml', 'a')
        link = 'sectors/' + year
        input = sitemap(link)
        sitemap_file.write(input)
        sitemap_file.close()

        entries = []
        if year == 'all':
            total = query_db_one('SELECT round(sum(usd_disbursement * 1000000),2) as total, crsid, sectorname from crs order by total desc')

            for u in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, crsid, sectorname, sectorcode, count(sectorname) as activities from crs where usd_commitment > 0 group by sectorname order by main_value desc'):
                d = dict(u.items())
                d['treearea'] = (d['main_value'] / total) * 190
                d = tremapCalc(d)
                entries.append(d)
        else:
            total = query_db_one('SELECT round(sum(usd_disbursement * 1000000),2) as total, crsid, sectorname from crs where Year = {0} order by total desc'.format(year))

            for u in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, crsid, sectorname, sectorcode, count(sectorname) as activities from crs where usd_commitment > 0 and Year = {0} group by sectorname order by main_value desc'.format(year)):
                d = dict(u.items())
                d['treearea'] = (d['main_value'] / total) * 190
                d = tremapCalc(d)
                entries.append(d)

        return render_template('sectors.html', entries=entries, total=total, var=var)


@app.route('/sector/<schwerpunkt>/')
def show_schwerpunkt(schwerpunkt):

        sitemap_file = open('sitemap.xml', 'a')
        link = 'sector/' + schwerpunkt
        input = sitemap(link)
        sitemap_file.write(input)
        sitemap_file.close()

        toppurpose = query_db('select sum(usd_disbursement * 1000000) as total, purposecode, purposename from crs where sectorcode = {0} group by purposename order by total desc limit 5'.format(schwerpunkt))

        result_top = len(toppurpose)
        sectorYearPrep = "SELECT Year, "

        i = 1
        for s in toppurpose:
            q = "SUM(CASE WHEN purposecode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector" % (s['purposecode'])
            sectorYearPrep = sectorYearPrep + q + str(i)
            if i < result_top:
                    sectorYearPrep = sectorYearPrep + ","
            i += 1

        sectorYearPrep = sectorYearPrep + " from crs group by Year"

        sectoryears = query_db(sectorYearPrep)

        gesamt = []
        for row in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as total, crsid, sectorname, sectorcode, recipientname as land, recipientcode, count(sectorname) as activities from crs where sectorcode = {0} and usd_commitment > 0 and Year = {1}'.format(schwerpunkt, str(g.year))):
            d = dict(row.items())
            gesamt.append(d)

        entries = []
        for u in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, crsid, purposename, sectorcode, recipientname as country, recipientcode, count(sectorname) as activities from crs where sectorcode = {0} and Year = {1} and usd_commitment > 0 group by purposename order by main_value desc'.format(schwerpunkt, str(g.year))):
            d = dict(u.items())
            d['treearea'] = (d['main_value'] / gesamt[0]['total']) * 170
            d = tremapCalc(d)
            entries.append(d)

        purpose_hist = query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, crsid, purposename, sectorcode, recipientname as land, recipientcode, count(sectorname) as activities from crs where sectorcode = {0} and usd_commitment > 0 group by purposename order by main_value desc'.format(schwerpunkt))

        countries = []
        for rows in query_db('SELECT round(sum(usd_disbursement * 1000000),2) as main_value, crsid, sectorname, sectorcode, recipientname as country, recipientcode, count(sectorname) as activities from crs where sectorcode = {0} and usd_commitment > 0 group by recipientname order by main_value desc limit 10'.format(schwerpunkt)):
            d = dict(rows.items())
            countries.append(d)

        return render_template('sector.html', entries=entries, gesamt=gesamt, countries=countries, sectoryears=sectoryears, toppurpose=toppurpose)


@app.route('/trends/')
def show_trends():

    hitlist = query_db('SELECT count(recipientcode) as total_activities, recipientname as land, recipientcode, round(sum(usd_disbursement * 1000000)) as total_sum from crs where Year between 2000 and ' + str(g.year) + ' and recipientname not like "%regional%" group by recipientname order by total_sum desc limit 20')

    aktuell = query_db('SELECT count(recipientcode) as total_activities, recipientname as land,recipientcode,round(sum(usd_disbursement * 1000000)) as total_sum from crs where Year = ' + str(g.year) + ' and recipientname not like "%regional%" group by recipientname order by total_sum desc limit 20')

    topsector = query_db('select sum(usd_disbursement * 1000000) as total, sectorname, sectorcode from crs group by sectorname order by total desc limit 5')

    sectorYearPrep = 'SELECT Year, SUM(CASE WHEN sectorcode = %s  THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector1, SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector2,SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector3,SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector4, SUM(CASE WHEN sectorcode = %s THEN round(usd_disbursement * 1000000) ELSE 0 END) AS sector5 from crs group by Year' % (topsector[0]['sectorcode'], topsector[1]['sectorcode'], topsector[2]['sectorcode'], topsector[3]['sectorcode'], topsector[4]['sectorcode'])

    regions = query_db("SELECT Year, SUM(CASE WHEN regionname = 'Middle East' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't1', SUM(CASE WHEN regionname = 'Europe' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't2', SUM(CASE WHEN regionname = 'Far East Asia' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't3', SUM(CASE WHEN regionname = 'North & Central America' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't4', SUM(CASE WHEN regionname = 'North of Sahara' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't5', SUM(CASE WHEN regionname = 'Oceania' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't6', SUM(CASE WHEN regionname = 'South & Central Asia' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't7', SUM(CASE WHEN regionname = 'South America' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't8', SUM(CASE WHEN regionname = 'South of Sahara' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't9', SUM(CASE WHEN regionname = 'Unspecified' THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't10' from crs group by Year")

    donors = query_db("SELECT Year, SUM(CASE WHEN donorcode = 302 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't1', SUM(CASE WHEN donorcode = 701 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't2', SUM(CASE WHEN donorcode = 905 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't3', SUM(CASE WHEN donorcode = 918 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't4', SUM(CASE WHEN donorcode = 5 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't5', SUM(CASE WHEN donorcode = 4 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't6', SUM(CASE WHEN donorcode = 12 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't7', SUM(CASE WHEN donorcode = 7 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't8', SUM(CASE WHEN donorcode = 50 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't9', SUM(CASE WHEN donorcode = 10 THEN round(usd_disbursement * 1000000) ELSE 0 END) AS 't10' from crs group by Year")

    sectoryears = query_db(sectorYearPrep)

    return render_template('trends.html', sectoryears=sectoryears, regions=regions, hitlist=hitlist, topsector=topsector, aktuell=aktuell, donors=donors)


@app.route('/disclaimer/')
def show_disclaimer():
    return render_template('disclaimer.html')


@app.route('/feedback/')
def show_spenden():
    return render_template('feedback.html')


@app.route('/about/')
def show_ueber():
    return render_template('about.html')


@app.route('/error.html')
def show_error():
    return render_template('error.html')

if __name__ == '__main__':
        app.run(host='0.0.0.0')
