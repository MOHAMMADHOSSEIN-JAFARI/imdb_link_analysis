# -*- coding: utf-8 -*-
"""imdblinkanalysis.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ip6gYP6kJNodu32MHUTHA-965b2QIFKw
"""

import pandas as pd
import numpy as np
from tqdm import tqdm

import re, sys
from operator import add
!pip install pyspark
import pyspark
from matplotlib import pyplot as plt
from pyspark.sql import Row

from pyspark.sql import SparkSession
!pip install graphframes
from graphframes import GraphFrame
import networkx as nx


import json
import zipfile
import os
import zipfile
from pprint import pprint

os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages graphframes:graphframes:0.8.0-spark3.0-s_2.12 pyspark-shell"
)
spark = SparkSession.builder \
                    .appName("IMDB Dataset Project") \
                    .config("spark.memory.offHeap.enabled",True) \
                    .config("spark.memory.offHeap.size","16g") \
                    .config("spark.jars.packages", "graphframes:graphframes:0.8.0-spark3.0-s_2.12") \
                    .getOrCreate()
spark

api_token = {"username":"amirrezadashtigenave","key":"c66368dee306274ca671fba6e60fb28b"}

kaggle_path = '/root/.kaggle/'
dataset_path = './ashirwadsangwan/'
# Check whether the specified path exists or not
if not os.path.exists(kaggle_path):
  # Create a new directory because it does not exist 
  os.makedirs(kaggle_path)
  print("The new directory is created!")

with open(kaggle_path + 'kaggle.json', 'w') as file:
    json.dump(api_token, file)
!chmod 600 /root/.kaggle/kaggle.json
!kaggle datasets download -d ashirwadsangwan/imdb-dataset

if not os.path.exists(dataset_path):
  # Create a new directory because it does not exist 
  os.makedirs(dataset_path)
  print("The new directory is created!")

with zipfile.ZipFile('./imdb-dataset.zip', 'r') as zip_ref:
    zip_ref.extractall('./ashirwadsangwan/')

title_basics = spark.read.csv("./ashirwadsangwan/title.basics.tsv/data.tsv", sep=r'\t', header=True)
print(title_basics.count())

fig = plt.figure(figsize =(12, 10))
plt.pie(title_basics.pandas_api().titleType.value_counts().values\
        ,autopct='%1.1f%%'\
        ,labels = title_basics.pandas_api().titleType.value_counts().keys().to_numpy())
plt.show()

nodes = title_basics.rdd.map(lambda x: (x[0], x[1]))
# nodes = title_basics.rdd.map(lambda x: (x[2], x[1]))
nodes = nodes.filter(lambda x: x[1] == "movie").map(lambda x: x[0])
number_of_nodes = nodes.count()

title_principals = spark.read.csv("./ashirwadsangwan/title.principals.tsv/data.tsv", sep=r'\t', header=True)

title_principals.createOrReplaceTempView("title_principals")
title_basics.createOrReplaceTempView("title_basics")
# sql_df = spark.sql("Select t1.*, t2.* from title_principals as t1 INNER JOIN title_basics as t2 ON t1.tconst = t2.tconst where t2.titleType= 'movie'")
sql_df = spark.sql("Select t1.*, t2.* from title_principals as t1 INNER JOIN title_basics as t2 ON t1.tconst = t2.tconst where t2.titleType= 'movie' and t2.startYear > '2021'")

cast_id_to_movie_list = sql_df.rdd.map(lambda x: (x[2],x[0], x[3]))\
                   .filter(lambda x: x[2] == "actor" or x[2] == "actress")\
                   .map(lambda x: (x[0],x[1]))\
                   .groupByKey()\
                   .map(lambda x : (x[0], list(x[1])))

# cast_id_to_movie_list = sql_df.rdd.map(lambda x: (x[2],x[8], x[3]))
#                    .filter(lambda x: x[2] == "actor" or x[2] == "actress")\
#                    .map(lambda x: (x[0],x[1]))\
#                    .groupByKey()\
#                    .map(lambda x : (x[0], list(x[1])))\
# print(cast_id_to_movie_list.take(2))

movie_id_to_movie_id = cast_id_to_movie_list.map(lambda x: [(a, b) for a in x[1] for b in x[1] if a!=b]).flatMap(lambda x: x).distinct()
# movie_id_to_movie_id.take(5)

"""<h3> Creating GraphFrame object </h3>"""

row = Row("id")
v = nodes.map(row).toDF()
e = movie_id_to_movie_id.toDF(["src", "dst"]).dropDuplicates()
g = GraphFrame(v, e)

"""<h3>Calculating pagerank using GraphFrames package</h3>

"""

graphframes_pagerank_results = g.pageRank(resetProbability=0.15, maxIter=10)

sum_of_graphframes_pagerank_values = graphframes_pagerank_results.vertices.rdd.map(lambda x: x[1]).reduce(lambda x,y: x+y)

print(sum_of_graphframes_pagerank_values)
print(number_of_nodes)

"""<h3>Showing most important nodes:</h3>

"""
# Three approaches are defiend here to compare the PageRanks.
graphframes_pagerank_results.vertices.orderBy("pagerank", ascending=False).show(20)

"""<h3>Least important nodes:</h3>"""

graphframes_pagerank_results.vertices.orderBy("pagerank", ascending=True).show(20)

graphframes_pagerank_results.vertices.show(20)

"""<h3>Now, we build the graph for the second time, but this time we are using the ***networkx*** library. The purpose is to calculate the pagerank algorithm with a different library to observe and compare the results.</h3>"""

myGraph = nx.Graph()
myGraph = nx.from_pandas_edgelist(e.toPandas(), 'src', 'dst')

"""<h3>Calculating pagerank for the second time using networkx library.</h3>"""

networkx_pagerank_results = nx.pagerank(myGraph, alpha=0.85, max_iter=10)

sum_of_graphframes_pagerank_values = sum(networkx_pagerank_results.values())
print(sum_of_graphframes_pagerank_values)

sorted_pagerank_results = dict(sorted(networkx_pagerank_results.items(), key=lambda item: item[1], reverse=True))
pprint( list(sorted_pagerank_results.items())[:20])

"""<h3>As it is shown, the results of the algorithms are similar.</h3>

<h3> This function gets an nx.graph object and a list of pageranks as arguments and plots the graph.</h3>
"""

def plot_graph(graph, page_ranks):
    pos = nx.random_layout(graph)
    plt.figure(3,figsize=(100,100)) 
    nx.draw(graph,node_color=list(page_ranks.values()), cmap=plt.cm.coolwarm, with_labels=True, node_size=5000)
    plt.savefig("Graph.png", format="PNG")

"""<h2>In this step,we are going to plot a small sample of the original graph with a cool-warm color map that shows the value of pagerank.<h2>
<br>
<h3>In the generated image below, nodes(movies) with more connecting edges are warmer.</h3>
"""

myGraph.remove_edges_from(list(myGraph.edges)[100:]) # Keeping only 100 edges
print(myGraph.number_of_edges())
myGraph.remove_nodes_from(list(myGraph.nodes)[100:]) # Keeping only 100 nodes
print(myGraph.number_of_nodes())
pr2 = nx.pagerank(myGraph, alpha=0.85) # calculating the pagerank on the small graph
plot_graph(myGraph, pr2)

def compute_distance(old_vector,new_vector):
    old_vector = list(old_vector.values())
    new_vector = list(new_vector.values())
    result = sum([(a - b)**2 for a, b in zip(old_vector, new_vector)])
    print(result)
    return result

def compute_page_rank(edges_rdd, nodes_count, damping_factor: float = 0.85, max_iter: int = 10, tolerance = 10e-10):
    out_degree = edges_rdd.countByKey()
    M = edges_rdd.map(lambda x:(x[0],x[1],1/out_degree[x[0]]))
    M_hat = M.map(lambda x: (x[0], x[1], damping_factor * x[2] + (1 - damping_factor) / nodes_count))
    MT = M_hat.map(lambda x: (x[1],x[0],x[2]))
    vector = dict(MT.map(lambda x: (x[0],1/(nodes_count))).collect())
    old_vector = dict(MT.map(lambda x: (x[0],1)).collect())
    i=1
    while i <= max_iter and compute_distance(old_vector, vector) >= tolerance:
        new_vector = MT.map(lambda x:(x[0],(x[2]*vector[x[1]])))\
                      .reduceByKey(lambda x,y: x+y)
        old_vector = vector
        vector = dict(new_vector.map(lambda x: (x[0], x[1])).collect())
        i+=1
    return vector

result = compute_page_rank(movie_id_to_movie_id, number_of_nodes)

my_page_rank = dict(sorted(result.items(), key=lambda item: item[1], reverse=True))
pprint( list(my_page_rank.items())[:20])

def compute_similarity(a, b, threshold: int = 4):
    total = 0
    for item in a:
        if item in b:
            for i in range(0,threshold):
                if a.index(item) == abs((i - b.index(item))) or a.index(item) == (i + b.index(item)):
                    total +=1
                    break
    return total/len(a)

a = graphframes_pagerank_results.vertices.orderBy("pagerank", ascending=False).rdd.map(lambda x: x[0]).take(20)
b = list(my_page_rank.keys())[:20]

compute_similarity(a, b, 2)

