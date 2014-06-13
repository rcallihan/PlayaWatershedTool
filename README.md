Playa Watershed Tool
==================

This python add-in script delineates watersheds for polygon landsape features such as playa lakes or wetlands. The output watershed polygons are assigned an ID that relates to original input feature.   

Inputs: 1) A polygon shapefile with one or more features 2) DEM
Output: A polygon shapefile representing the watersheds of the input features. 

###Non-Nested###

This version calculates the watersheds of mutliple polygons at once using Spatial Analyst's Watershed tool. Resulting watersheds are not nested and do not overlap. 

###Nested###

This script iterates through each polygon, creating unique but nested watersheds for each feature. Individual watershed polygons are merged into a single feature class. 

This script is process intensive.


