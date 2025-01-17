# -*- coding: utf-8 -*-
"""Thesis_sentiment_analysis fine-tuned BERTje

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10-eOd1ADnRbjviJtqDBclftWPneaIGw4
"""

from google.colab import drive
drive.mount('/content/drive')

!pip install farm #source: https://github.com/deepset-ai/FARM

import numpy as np
import pandas as pd
import farm
import glob
import pickle

from farm.modeling.tokenization import Tokenizer
from farm.data_handler.processor import TextClassificationProcessor
from farm.data_handler.data_silo import DataSilo
from farm.modeling.language_model import LanguageModel
from farm.modeling.prediction_head import TextClassificationHead
from farm.modeling.adaptive_model import AdaptiveModel
from farm.utils import set_all_seeds, MLFlowLogger, initialize_device_settings
from farm.train import Trainer
from farm.infer import Inferencer
from farm.modeling.optimization import initialize_optimizer

def doc_classifcation():
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO)
    
    ml_logger = MLFlowLogger(tracking_uri="https://public-mlflow.deepset.ai/")
    ml_logger.init_experiment(experiment_name="Public_FARM", run_name="Run_doc_classification")



from transformers import RobertaTokenizer, RobertaForSequenceClassification
tokenizer = RobertaTokenizer.from_pretrained("pdelobelle/robbert-v2-dutch-base", do_lower_case = False)
lang_model = RobertaForSequenceClassification.from_pretrained("pdelobelle/robbert-v2-dutch-base")

from transformers import BertTokenizer, BertModel, TFAutoModel, AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("wietsedv/bert-base-dutch-cased")
lang_model = TFAutoModel.from_pretrained("wietsedv/bert-base-dutch-cased")  # Tensorflow

"""# **Train adaptive model on KTO data**"""

use_amp = None
device, n_gpu = initialize_device_settings(use_cuda=True, use_amp=use_amp)

import string
def remove_punctuations(text):
    for punctuation in string.punctuation:
        text = text.replace(punctuation, '')
    return text

test2 = pd.read_excel("/content/drive/MyDrive/Files/sentiment_excel.xlsx")
test2["text"] = test2["text"].str.encode('utf-8', 'ignore').str.decode('utf-8')
test2["text"] = test2["text"].apply(remove_punctuations)
test2["text"] = test2["text"].str.lower()
test2.to_csv(r'/content/drive/My Drive/Files/sentiment_v5.csv', index = False, header = True, sep = ";")

cols = pd.read_csv('/content/drive/My Drive/Files/sentiment_csv.csv', nrows=1).columns

#define processor and create dictionaries
label_list = ['positief', 'neutraal', 'negatief']

processor = TextClassificationProcessor(tokenizer=tokenizer,
                                        max_seq_len = 30, 
                                        data_dir="/content/drive/MyDrive/Files/",
                                        label_list = label_list,
                                        metric = "f1_macro",
                                        label_column_name = "sentiment",
                                        delimiter = ";",
                                        quote_char = '"',
                                        columns = ["text", "sentiment"],
                                        dev_filename = None,
                                        dev_split = 0.10)

dicts = processor.file_to_dicts(file='/content/drive/MyDrive/Files/sentiment_v5.csv')

#define test and train samples
split = pd.read_csv(r'/content/drive/MyDrive/Files/sentiment_v5.csv', delimiter=";")
train = split[:5660] #80%
test = split.tail(1415) #20%
train.to_csv(r'/content/drive/MyDrive/Files/train.tsv', index = False, header = True, sep = ";")
test.to_csv(r'/content/drive/MyDrive/Files/test.tsv', index = False, header = True, sep = ";")

#define datasilo
data_silo = DataSilo(processor = processor,
                     batch_size = 32)

#Create adaptive model
#pretrained language model as basis
language_model = LanguageModel.load("wietsedv/bert-base-dutch-cased", language = 'Dutch') # n_added_tokens = 5
#language_model = lang_model

#prediction head on top that is suited for sentiment analysis (text classification)
prediction_head = TextClassificationHead(
    class_weights=data_silo.calculate_class_weights(task_name="text_classification",),
    num_labels=len(label_list))

#combine into model
model = AdaptiveModel(
    language_model=language_model,
    prediction_heads=[prediction_head],
    embeds_dropout_prob=0.1,
    lm_output_types=['per_sequence'],
    device=device)

#Create an optimizer
n_epochs = 1

model, optimizer, lr_schedule = initialize_optimizer(
    model = model,
    learning_rate = 3e-5,
    device = device,
    n_batches = len(data_silo.loaders["train"]),
    n_epochs = n_epochs,
    use_amp = use_amp)

#Feed everything into the trainer
evaluate_every = 100

trainer = Trainer(
    model = model,
    optimizer = optimizer,
    data_silo = data_silo,
    epochs = n_epochs,
    n_gpu = n_gpu,
    lr_schedule = lr_schedule,
    evaluate_every = evaluate_every,
    device = device)

trainer.train()

#Save the model
from pathlib import Path
save_dir = Path("saved_models/BERTje")
model.save(save_dir)
processor.save(save_dir)

#Load model and evaluate
basic_texts = [
               {"text": "ik vond het een hele goede service"},
               {"text": "ben helemaal niet geholpen ik zou deze app niet aanraden"},
               {"text": "ik weet het niet zo goed"}
]

model = Inferencer.load(save_dir)
result = model.inference_from_dicts(dicts=basic_texts)
print(result)

result