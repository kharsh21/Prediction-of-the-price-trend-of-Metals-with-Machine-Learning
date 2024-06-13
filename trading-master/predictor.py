from fastai.vision import *
import torch
from log import log

print("fastai version " + __version__)
print("torch version " + torch.__version__)

#from instruments import instrumentList, instruments

#path_to_model_export='/storage/candles/Model_export/'
#path_to_akt_image='/storage/candles/akt_candles/'
#classes=['0','L','S']

#instrument_no=4
#date_image='2019-12-19'
#instrumentName = instrumentList[instrument_no][0]
#instrumentFileName = instrumentToDirName(instrumentName)

def Do_prediction_from_file(image_file, model_path, model_fname, classes_list=['0','L','S']):
  log("    predict %s %s/%s" % (image_file, model_path, model_fname))
  img=open_image(image_file)
  learn=load_learner(model_path, model_fname)
  predicted_class, predicted_index, outputs = learn.predict(img)
  return classes_list[int(predicted_index)], outputs

#Do_prediction_from_file(path_to_akt_image+image_fname, path_to_model_export, model_fname )
# e.g. ('0', tensor([9.9822e-01, 1.2583e-03, 5.2431e-04]))

#def Do_prediction_from_image_obj(image_obj, model_path, model_fname, classes_list=['0','L','S']):
#    learn=load_learner(model_path, model_fname)
#    predicted_class, predicted_index, outputs = learn.predict(image_obj)
#    return classes_list[int(predicted_index)], outputs

#akt_img=open_image(path_to_akt_image+image_fname)
#Do_prediction_from_image_obj(akt_img, path_to_model_export, model_fname )
# e.g. ('0', tensor([0.9754, 0.0115, 0.0131]))

