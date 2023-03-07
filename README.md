This is the official source code of our paper, <br />
[LightX3ECG: A Lightweight and eXplainable Deep Learning System <br />for 3-lead Electrocardiogram Classification](https://drive.google.com/file/d/1eyFhzr0VDOi1IrJ4Cah8IuE00HiE32QG/view?usp=sharing), <br />
which is the 1st part of our project on Reduced-lead ECG Classification. Check out the 2nd part [here](https://github.com/lhkhiem28/X3ECGpp). 
# Source
## nets
## tools
### train.py
dataset : Dataset que se usará para entrenar el modelo. Puede ser CPSC-2018 o Chapman.
multilabel : Booleano que se usa para indicar si se usarán múltiples etiquetas.
num_gpus : Número de GPUs que se usarán durante el entrenamiento.