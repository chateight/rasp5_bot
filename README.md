# rasp5_bot

raspberry pi 5 chatbot(ras_bot) code

file directory structure is as follows

<img width="240" alt="directory_struct" src="https://github.com/user-attachments/assets/e4a32c05-bb74-4852-b78d-c6c7847f0e37" />

Flask server starts and accepts image recognition requests independently

Notes
1. you need to install additional files for voice recongnition and voise sysnthesis, like recongtion parameter file and Japanese dictionary for syntax analysis
2. to use different Python environment for main routine(integration directory) and an image recognition script(tflite directory) due to library confilict

