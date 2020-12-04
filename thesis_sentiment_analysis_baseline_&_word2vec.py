# -*- coding: utf-8 -*-
"""Thesis_sentiment_analysis baseline  & word2vec

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qts-hMtIs7vyR89BqMDyVjAWMSdE9NhU
"""

from google.colab import drive
drive.mount("/content/drive", force_remount=True)

!pip install transformers
!pip install sentence_transformers
!pip install pandas plotnine

import numpy as np
import pandas as pd
import re
import multiprocessing

import tensorflow as tf
import transformers
import torch
import sklearn
import plotly as py
import plotly.graph_objs as go
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import TfidfTransformer
from transformers import BertTokenizer, BertModel, TFAutoModel, AutoTokenizer
from transformers import RobertaTokenizer, RobertaForSequenceClassification
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import KNeighborsClassifier
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from plotnine import *
from time import time
from collections import defaultdict

from gensim.models import Word2Vec
from gensim.models import KeyedVectors
from gensim.models.phrases import Phrases, Phraser
from gensim.test.utils import get_tmpfile

#Define wordlist
def make_wordlist(sentences):
  wordlist = []
  for sentence in sentences:
    for word in sentence.split():
      if word not in wordlist:
        wordlist.append(word)
  return wordlist

def filter_stopwords(sentence, stopwords):
  filter =  [word for word in sentence.split() if word not in stopwords]
  return " ".join(filter)

#Define non-numeric characters deletion
def alpha(sentence):
  sentence = sentence.split()
  filter = [word for word in sentence if word.isalpha() != False]
  return " ".join(filter)

explain = pd.read_excel(r"/content/drive/My Drive/Files/NPS_toelichting.xlsx")['Zou u uw antwoord kunnen toelichten?'].astype(str)
good = pd.read_excel(r"/content/drive/My Drive/Files/NPS_goede_punten.xlsx")['Wat vond u goed aan de dienst?'].astype(str)
suggest = pd.read_excel(r"/content/drive/My Drive/Files/NPS_verbeterpunten.xlsx")['Heeft u nog verbeterpunten/suggesties/tips voor de dienst?'].astype(str)

data = np.concatenate((explain, good), axis = None)
data = np.concatenate((data, suggest), axis = None)

test = pd.read_csv(r"/content/drive/MyDrive/Files/test.tsv", sep = ";")
test_text = test['text'].astype(str)
test_category = test['sentiment']

#ex_data = pd.read_excel(r"/content/drive/My Drive/Files/toelichting_voorbeelden_uitdata.xlsx")
#good_ex_data = pd.read_excel(r"/content/drive/My Drive/Files/goedepunten_voorbeelden_uitdata.xlsx")
#suggest_ex_data = pd.read_excel(r"/content/drive/My Drive/Files/suggesties_voorbeelden_uitdata.xlsx")

#ex_art = pd.read_excel(r"/content/drive/My Drive/Files/toelichting_voorbeelden_artificial.xlsx")
#good_ex_art = pd.read_excel(r"/content/drive/My Drive/Files/goedepunten_voorbeelden_artificial.xlsx")
#suggest_ex_art = pd.read_excel(r"/content/drive/My Drive/Files/suggesties_voorbeelden_artificial.xlsx")

#all_sentences = ex_art['exp_allsentences']
#category = ex_art['exp_categorie']
#category_num = ex_art['exp_categorienummer']

stopwords = np.loadtxt("/content/drive/My Drive/Files/stopwords.txt", delimiter = ",", dtype = str)
pos = np.loadtxt("/content/drive/My Drive/Files/positive_words_nl.txt", skiprows = 1, dtype = str)
neg = np.loadtxt("/content/drive/My Drive/Files/negative_words_nl.txt", skiprows = 1, dtype = str)
words = np.loadtxt("/content/drive/My Drive/Files/words.txt", skiprows = 1, dtype= str)

pos_tag = ['pos']*len(pos)
neg_tag = ['neg']*len(neg)
tags = pos_tag + neg_tag

len(tags) == len(words)

#data['Zou u uw antwoord kunnen toelichten?'] = data['Zou u uw antwoord kunnen toelichten?'].astype(str)
#explanations = np.asarray(data["Zou u uw antwoord kunnen toelichten?"])

#find longest sentence
l = 0
for sentence in data:
  le = len(sentence.split())
  if le > l:
    l = le
#l = 207 words

word_freq = defaultdict(int)
for sent in data:
  for i in sent.split():
    word_freq[i] += 1
len(word_freq)
sorted(word_freq, key=word_freq.get,reverse=True)[:20]

"""**Preprocessing**"""

punctuation = '"#$%&\'()*+,-./:;<=>@[\\]^_`{|}~!?'

for nr in range(len(data)):
  data[nr] = alpha(filter_stopwords(data[nr], stopwords)).lower()

for nr in range(len(test_text)):
  test_text[nr] = alpha(filter_stopwords(test_text[nr], stopwords)).lower()

wordlist = make_wordlist(data)
print(len(wordlist)) #6833 unique words

word_freq = defaultdict(int)
for sent in data:
  for i in sent.split():
    word_freq[i] += 1
len(word_freq)

sorted(word_freq, key=word_freq.get, reverse = True)[:10]

"""# **Word2Vec**

**Create bi-grams**
"""

sent = [row.split() for row in data]
phrases = Phrases(sent, min_count=10, progress_per=10000)

sentences = phrases[sent]

for sentence in sentences[0:50]:
  print(sentence)

"""**Create word embeddings with Word2Vec (Gensim)**
* min count = 3 - remove most unusual words from training embeddings, like words ssssuuuuuuuppppppeeeeeerrrr', which actually stands for 'super', and doesn't need additional training
* window = 4 - Word2Vec model will learn to predict given word from up to 4 words to the left, and up to 4 words to the right
* size = 300 - size of hidden layer used to predict surroundings of embedded word, which also stands for dimensions of trained embeddings
* sample = 1e-5 - probability baseline for subsampling most frequent words from surrounding of embedded word
* negative = 20 - number of negative (ones that shouldn't have been predicted while modeling selected pair of words) words that will have their corresponding weights updated while training on specific training example, along with positive word
"""

#initialize the model and build vocabulary
w2v_model = Word2Vec(min_count = 15, #ignores all words with total absolute frequency lower than this
                     window = 5, #the maximum distance between the current and predicted word within a sentence
                     size = 8, #dimensionality of the feature vectors
                     sample = 1e-12, #the threshold for configuring which higher-frequency words are randomly downsampled. highly influential
                     alpha = -.03, #the initial learning rate
                     min_alpha = 0.0007, #learning rate will linearly drop to min_alpha as training progresses
                     negative = 20, #if > 0 negative sampling will be used, the int for negative specifies how many "noise words" should be drawn. 
                     workers = 10) #use this many worker threads to train the model (= faster training with multicore machines)

start = time()
w2v_model.build_vocab(sentences, progress_per = 50000) 
print("Time to build vocab: {} mins".format(round((time()-start) / 60, 2)))

#train the model
start = time()
w2v_model.train(sentences,
                total_examples = w2v_model.corpus_count, #count of sentences
                epochs = 6, #number of iterations (epochs) over the corpus
                compute_loss = True)

print("Time to train the model: {} mins".format(round((time()-start)/60, 2)))

w2v_model.get_latest_training_loss()

#look at which words are most similar to 'verpleegkundige'
w2v_model.wv.most_similar(positive=['app'])

#save the model
w2v_model.save("Word2vec.model")

#export preprocessed dataset for further steps (with replaced bigrams)
#sentences.to_csv('cleaned_dataset_sentiment.csv', index = False)



"""**K-means clustering**"""

from gensim.models import Word2Vec
from sklearn.cluster import KMeans

word_vectors = Word2Vec.load("/content/Word2vec.model").wv

model = KMeans(n_clusters = 2, max_iter = 1000, random_state = True, n_init = 50).fit(X=word_vectors.vectors)

word_vectors.similar_by_vector(model.cluster_centers_[1], topn = 20, restrict_vocab = None)

positive_cluster_center = model.cluster_centers_[0]
#neutral_cluster_center = model.cluster_centers_[1]
negative_cluster_center = model.cluster_centers_[1]

def cast_vector(row):
  return np.array(list(map(lambda x: x.astype('double'), row)))
  
words = pd.DataFrame(word_vectors.vocab.keys())
words.columns = ['words']
words['vectors'] = words.words.apply(lambda x: word_vectors.wv[f'{x}'])
words['vectors_typed'] = words.vectors.apply(cast_vector)
words['cluster'] = words.vectors_typed.apply(lambda x: model.predict([np.array(x)]))
words.cluster = words.cluster.apply(lambda x: x[0])

words['cluster_value'] = [1 if i==0 else -1 for i in words.cluster]
words['closeness_score'] = words.apply(lambda x: 1/(model.transform([x.vectors]).min()), axis=1)
words['sentiment_coeff'] = words.closeness_score * words.cluster_value

words.head(20)

words[['words', 'sentiment_coeff']].to_csv('sentiment_dictionary.csv', index=False)

word2vec_sentiment = pd.read_csv(r"/content/drive/MyDrive/Files/sentiment_dictionary.csv")
word2vec_sentiment

word2vec_sentiment.set_index('words').index.get_loc('drukke')

#Test
result = []
for sentence in test_text:
  sentiment = []
  for word in sentence.split():
    if word in list(word2vec_sentiment['words']):
      index = word2vec_sentiment.set_index('words').index.get_loc(word)
      score = word2vec_sentiment['sentiment_coeff'][index]
      sentiment.append(score)
  if len(sentiment) > 0:
    final_score = sum(sentiment)/len(sentiment)
    result.append(final_score)
  else:
    result.append(0)

label = []
for r in result:
  if r > 0:
    o = 'positief'
  if r == 0: 
    o = 'neutraal'
  if r < 0:
    o = 'negatief'
  label.append(o)

assert len(label) == len(test_text) == len(result) == len(test_category)

#Make dataframe
df = pd.DataFrame({'sentence':test_text, 'score':result, 'label':label})
df

#Get test results
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

y_true = test_category
y_pred = label
#labels = ['positief', 'neutraal', 'negatief']

cm = confusion_matrix(y_true, y_pred)#, labels = labels)
report = classification_report(y_true, y_pred)
print(report)

#Plot confusion matrix
import seaborn as sns
import matplotlib.pyplot as plt     
from matplotlib.pyplot import figure
ax= plt.subplot()
sns.heatmap(cm, annot=True, ax = ax, fmt = 'g'); #annot=True to annotate cells
sns.set(rc={'figure.figsize':(6,6)})

#Labels, title and ticks
ax.set_xlabel('Predicted labels');ax.set_ylabel('True labels');
ax.set_title('Confusion Matrix'); 
ax.xaxis.set_ticklabels(labels, rotation = 89); ax.yaxis.set_ticklabels(labels, rotation = 0);

"""# **Multilingual model 1**

"""

#Make word embeddings of positive and negative words and plot them
from sentence_transformers import SentenceTransformer, util
import torch

embedder = SentenceTransformer('xlm-r-bert-base-nli-stsb-mean-tokens')

embeddings = embedder.encode(words, convert_to_numpy = True)
#embeddings = np.reshape(embeddings, (len(words), 1, 768))
print(embeddings.shape)

#Dimensionality reduction
#source https://towardsdatascience.com/elmo-contextual-language-embedding-335de2268604
pca = PCA(n_components=50)
y = pca.fit_transform(embeddings)
y = TSNE(n_components=2).fit_transform(y)

#Static visualization
plot_data = pd.DataFrame({'x':y[:,0], 'y':y[:,1], 'Category':tags})
ggplot(plot_data, aes(x='x', y='y', color='Category')) + geom_point(size = 1)

"""# **simple approach**

"""

def sentiment(sentence):
  score = 0
  for word in sentence.split():
    if word in pos:
      score += 1
      #print("positive word +1:", word)
    if word in neg:
      score -= 1
      #print("negative word -1:", word)
  #print(sentence, sentiment)
  if score == 0:
    s = 'neutraal'
  if score > 0:
    s = 'positief'
  if score < 0:
    s = 'negatief'
  return score, s

sentiment_scores = []
sentiments = []
for sentence in data[0:100]:
  output = sentiment(sentence)
  score = output[0]
  label = output[1]
  sentiment_scores.append(score)
  sentiments.append(label)

d = {'sentence':data[0:100], 'sentiment score':sentiment_scores, 'sentiment':sentiments}
df = pd.DataFrame(data = d)

df

#TEST SET
#Get sentiment scores
sentiments= []
for sentence in test_text:
  output = sentiment(sentence)
  sentiments.append(output[1])

assert len(sentiments) == len(test_text)

#Get evaluation measures
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

y_true = test_category
y_pred = sentiments
#labels = ['positief', 'neutraal', 'negatief']

cm = confusion_matrix(y_true, y_pred)#, labels = labels)
report = classification_report(y_true, y_pred)
print(report)

#Plot confusion matrix
import seaborn as sns
import matplotlib.pyplot as plt     
from matplotlib.pyplot import figure
ax= plt.subplot()
sns.heatmap(cm, annot=True, ax = ax, fmt = 'g'); #annot=True to annotate cells
sns.set(rc={'figure.figsize':(6,6)})

labels = ['negatief', 'neutraal', 'positief']

#Labels, title and ticks
ax.set_xlabel('Predicted labels');ax.set_ylabel('True labels');
ax.set_title('Confusion Matrix'); 
ax.xaxis.set_ticklabels(labels, rotation = 89); ax.yaxis.set_ticklabels(labels, rotation = 0);

#RobBERT model
tokenizer_robbert = RobertaTokenizer.from_pretrained("pdelobelle/robbert-v2-dutch-base")
model_robbert = RobertaForSequenceClassification.from_pretrained("pdelobelle/robbert-v2-dutch-base")

tokenized_input = tokenizer_robbert(list(data[0:250]), return_tensors = "pt", padding = True)
outputs = model_robbert(**tokenized_input, output_hidden_states = True)