# Cat-Detector
A local network security camera with Tensorflow object detection for automatic cat detection using Raspberry Pi.


`Main_RPI.py` Runs on a Raspberry Pi (OW in my case) with a connected camera. The PI captures images and sends them via a socket connection to a main `base` computer for processing. Look for the `address` variable and be sure to change it to the name of your computer, eg `Jacks-Computer.local`

`Main_Base.py` should be running on that local `base` computer. This program opens a socket and listens for incoming images. Those images are received and run through the pre-trained `yolo_v8_m_pascalvoc` object detection model. The results are superimposed on the image and added to a locally saved dataframe. 

https://github.com/Jack-Baumgartel/Cat-Detector/blob/main/Example.jpg
