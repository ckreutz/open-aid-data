OpenAidData.org
=============

OpenAidData.org provides detailed developing aid finance data from around the world.

Background
----------
**[Blog post about the project](http://www.crisscrossed.net/2014/04/24/launch-openaiddata/)**

App
----------

The app is implemented by using the Python microframework Flask. It is a lightweight app, in which all the action resides in one file: *openaid.py* Flask is only used for development and to render all of the website files (Frozen-Flask) completely, which can then be deployed to any web server. The interactive part then is done at the client side by Javascript thanks to the [openspending project](https://github.com/openspending). 

Data
---------
The CRS data can be downloaded at the [OECD CRS website](http://stats.oecd.org/Index.aspx?datasetcode=CRS1). The complete raw data set is a bit hidden; click on the above link in the menu on export and then on "related files". The IATI data can be downloaded at the [IATI registry](http://www.iatiregistry.org/). The total data is way over 2GB. 
