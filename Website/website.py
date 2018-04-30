from flask import Flask, request, render_template, url_for, redirect, jsonify
import json
import html2text
import requests
from threading import Thread
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import pandas as pd
import os
from bs4 import BeautifulSoup, SoupStrainer
from pymongo import MongoClient
import re
import sentiment

client = MongoClient()
client = MongoClient('localhost', 27017)
db = client['web_history_data']

target = []
docs = []
for file in os.listdir("training_set"):
    with open("./training_set/" + file) as f:
        docs.append(f.read())
    target.append(file.split("_")[-1])
target = [tar[0] for tar in target]
# print(len(target))
# print(sum([1 if x == "R" else 0 for x in target]))
classes = set()
for t in target:
    classes.add(t)
classes = sorted(list(classes))
convote_vectorizer = TfidfVectorizer(stop_words='english', min_df=0,max_df=0.8, ngram_range=(1,8))
convote_word_vectors = convote_vectorizer.fit_transform(docs)
classifier = MultinomialNB().fit(convote_word_vectors, target)


app = Flask(__name__)


def loadDB(link):

    h = html2text.HTML2Text()
    link = link[0]
    print(link)

    # Ignore converting links from HTML
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_anchors = True
    h.skip_internal_links = True

    website_text = []

    try:
        child_links = []
        if link[:4] == 'http':
            html = requests.get(link)
            html = html.text
            parent_html = str(html);
            website_text.append([link, h.handle(html).strip().replace("\n", " ")])
        
        soup = BeautifulSoup(html, "html.parser")
        for childLink in soup.findAll('a'):
            if childLink.get('href')[:4] == 'http':
                child_links.append(childLink.get('href'))

        update_query = {'parent_url': link}
        class_data = classifyForDB(website_text)
        post_data = {
            'parent_url': link,
            'parent_text': h.handle(html).strip(),
            'parent_html': parent_html,
            'classify_data': class_data,
            'child_links': child_links
            }

        result = db.webtext.update(update_query, post_data, upsert=True)
        print(result)

    except Exception as e:
        print(e)

    return website_text


def initialLoadDB(history):
    chromeData = history
    h = html2text.HTML2Text()

    # Ignore converting links from HTML
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_anchors = True
    h.skip_internal_links = True

    website_text = []

    for link in chromeData:
        try:
            if "google.com" in link['url'] or "slack.com" in link['url']:
                continue
            query = db.webtext.find({"parent_url": link['url']})
            if(query.count() == 0):
                child_links = []
                if link['url'][:4] == 'http':
                    html = requests.get(link['url'])
                    html = html.text
                    parent_html = str(html);
                    plain_text = h.handle(html).strip()
                else: 
                    continue
                
                soup = BeautifulSoup(html, "html.parser")
                children = set()
                for childLink in soup.findAll('a'):
                    if childLink.get('href') is not None and childLink.get('href')[:4] == 'http':
                        if childLink.get('href').count("/") > 4 or ".html" in childLink.get('href'):
                            children.add(childLink.get('href'))

                update_query = {'parent_url': link['url']}
                class_data = classifyForDB([link['url'], plain_text])
                sent, magnitude = sentiment.analyze(plain_text)
                post_data = {
                    'parent_url': link['url'],
                    'parent_text': plain_text,
                    'parent_html': parent_html,
                    'classify_data': class_data,
                    'child_links': list(children)
                    }

                result = db.webtext.update(update_query, post_data, upsert=True)

                print(result)
            else:
                continue

        except Exception as e:
            print(e)

def getUrls(urls):
    h = html2text.HTML2Text()

    # Ignore converting links from HTML
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_anchors = True
    h.skip_internal_links = True

    website_text = []

    for url in urls:
        # try:
            query = db.webtext.find({"parent_url": url})
            if(query.count() == 0):
                child_links = []
                if url[:4] == 'http':
                    html = requests.get(url)
                    html = html.text
                    parent_html = str(html);
                    plain_text = h.handle(html).strip()
                else: 
                    continue
                
                soup = BeautifulSoup(html, "html.parser")
                children = set()
                for childLink in soup.findAll('a'):
                    if childLink.get('href') is not None and childLink.get('href')[:4] == 'http':
                        if childLink.get('href').count("/") > 4 or ".html" in childLink.get('href'):
                            children.add(childLink.get('href'))

                update_query = {'parent_url': url}
                class_data = classifyForDB([url, plain_text])
                sent, magnitude = sentiment.analyze(plain_text)

                post_data = {
                    'parent_url': url,
                    'parent_text': plain_text,
                    'parent_html': parent_html,
                    'classify_data': class_data,
                    'sentiment': sent,
                    'magnitude': magnitude,
                    'child_links': list(children)
                    }

                result = db.webtext.update(update_query, post_data, upsert=True)
                result = {k : post_data[k] for k in ["classify_data", "sentiment", "magnitude"]}

                website_text.append(result)
            else:
                data = query.next()
                result = {k : data[k] for k in ["classify_data", "sentiment", "magnitude"]}
                website_text.append(result)

        # except Exception as e:
        #     print(e)

    return website_text

def get_parent_urls():
    
    output_array = []

    cursor1 = db.webtext.find()
    for record in cursor1:
        output_array.append([record["parent_url"],
                record["parent_text"]])

    return output_array

def get_parents():
    
    output_array = []

    cursor1 = db.webtext.find()
    for record in cursor1:
        output_array.append(record)

    return output_array

def get_child_urls():
    
    output_array = []

    # cursor1 = db.webtext.find()
    # for record in cursor1:
    #     output_array.append([record["parent_url"],
    #             record["parent_text"]])

    return output_array

@app.route('/')
def index():

    return "Hello, World"

@app.route('/initialUpdate', methods = ['POST'])
def initialUpdate():
        
    history = json.loads(request.form.get("history", "[]"))
    initialLoadDB(history)
    return jsonify(dict(result = "success"))


@app.route('/words', methods=["POST"])
def graph_words():
    try:
        # with open("parsed.txt") as f:
        #     docs = json.loads(f.read())["results"]
        docs = get_parent_urls()
        vectorizer = TfidfVectorizer(stop_words='english', min_df=1,max_df=0.8)
        word_vectors = vectorizer.fit_transform([x[0] for x in docs if len(x[0]) > 100])

        terms = vectorizer.get_feature_names()

        terms = [term for term in terms if term.isalpha()]

        counter = CountVectorizer(stop_words='english', vocabulary=terms)
        count_vectors = counter.fit_transform([x[0] for x in docs if len(x[0]) > 100])
        print(terms)
        counts = count_vectors.todense().sum(axis=0)
        #sorted_counts = counts.argsort()
        totals = []

        for i in range(counts.shape[1]):
            totals.append([terms[i], counts[0,i]])
        totals = sorted(totals, key=lambda x: x[1])[::-1]
        totals = [{"text": x[0], "size": int(x[1])} for x in totals]
        return jsonify(dict(result=totals))
    except Exception as e:
        return jsonify(dict(Error=str(e)))


@app.route('/classify', methods=["POST"])
def classify():
    hist = get_parent_urls()

    vecs = convote_vectorizer.transform([x[1] for x in hist if len(x[1]) > 50])
    pred = classifier.predict(vecs)
    prob = classifier.predict_proba(vecs)
    counts = prob.sum(axis=0)
    #print(counts)
    #print(counts.shape)
    totals = []
    #print(counts[0])
    for i in range(counts.shape[0]):
        totals.append([classes[i], counts[i]])
    totals = sorted(totals, key=lambda x: x[1])[::-1]
    total_prob = sum([x[1] for x in totals])
    totals = [{"type": x[0], "value": float(x[1]) / total_prob * 100} for x in totals]
    for i in range(len(totals)):
        if totals[i]["type"] == "R":
            totals[i]["color"] = "#E91D0E"
        elif totals[i]["type"] == "D":
            totals[i]["color"] = "#232066"
        else:
            totals[i]["color"] = "#a0a5b2"
    return jsonify(dict(result=totals))

@app.route('/sentiment', methods=["POST"])
def sentiment_analysis_endpoint():
    hist = get_parents()
    total = 0
    neutral = 0
    positive = 0
    negative = 0
    count = 0
    for res in hist:
        if "sentiment" in res:
            count += 1
            if res["sentiment"] == 0:
                neutral += res["magnitude"] / 10
            elif res["sentiment"] > 0:
                positive += res["magnitude"] * res["sentiment"]
            else:
                negative += -res["magnitude"] * res["sentiment"]
    total = neutral + positive + negative
    totals = [{"type": "Positive", "value": positive / total * 100, "color": "mediumseagreen"},
              {"type": "Negative", "value": negative / total * 100, "color": "firebrick"},
              {"type": "Neutral", "value": neutral / total * 100, "color": "#a0a5b2"}
    ]

    return jsonify(dict(result=totals, count=count))

@app.route('/classify_one', methods=["GET"])
def classify_one():

    url = request.args.get("url", "")
    if len(url) == 0:
        return jsonify(dict(error= "Invalid url"))
    print(url)
    print(url.split("?")[0])
    hist = getUrls([url.split("?")[0]])
    if len(hist) == 0:
        return jsonify(dict(error= "Unreachable urls"))
    print(hist)
    return jsonify(dict(result=hist))


def classifyForDB(parent_data):

    vecs = convote_vectorizer.transform([parent_data[1]])
    pred = classifier.predict(vecs)
    prob = classifier.predict_proba(vecs)
    counts = prob.sum(axis=0)
    #print(counts)
    #print(counts.shape)
    totals = []
    #print(counts[0])
    for i in range(counts.shape[0]):
        totals.append([classes[i], counts[i]])
    totals = sorted(totals, key=lambda x: x[1])[::-1]
    total_prob = sum([x[1] for x in totals])
    totals = [{"type": x[0], "value": float(x[1]) / total_prob * 100} for x in totals]
    for i in range(len(totals)):
        if totals[i]["type"] == "R":
            totals[i]["color"] = "#E91D0E"
        elif totals[i]["type"] == "D":
            totals[i]["color"] = "#232066"
        else:
            totals[i]["color"] = "#a0a5b2"

    return totals


if __name__ == "__main__":
    app.run(threaded=True)
    
