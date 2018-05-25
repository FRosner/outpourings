---
title: Handwritten Digit Recognition Using Convolutional Neural Networks
published: false
description:
tags: showdev, deeplearning, scala, javascript
---

# Introduction

In this blog post I want to share a small application I developed that classifies images of hand written digits, together with the lessons learned while developing it. When it comes to machine learning, in the past I have mainly worked with text data. Pattern recognition on image data is new to me but I think it is a very useful skill.

The post is structured as follows. [TODO]

# Working With Image Data

Machine learning algorithms expect data to be represented in some numerical format that the computer can understand. When using probabilistic models, e.g., your data has to fit into the format expected by the distributions your model is using.

As an example consider a multinomial mixture model. To utilize this type of model, you need to be able to convert your data into counts. In text this can be achieved by introducing a counting variable for each possible word of each cluster in each possible document. This model is very simple and works great for many use cases. However it has one big disadvantage: It discards a lot of information, e.g. term cooccurrences and position within the document.

For image data this problem is even greater. While you can still determine whether an email is spam by just looking at the word counts, recognizing images with cats is much harder when only counting the number of pixels having a specific color. While text data is 1-dimensional, i.e. a sequence of terms, images are at least 2-dimensional, i.e. a matrix of pixels, and contain a lot more information in the spatial relation of the pixels.

Luckily there are other models we can use that take spacial information into account. A very commonly used type of models are [Convolutional Neural Networks](http://cs231n.github.io/convolutional-networks/) (CNN). While research in this area is ongoing for some time now [cnn], the era of GPU based training lead to major break-throughs in terms of model performance in the recent years [mcd].

How do we represent a raw image in the computer? A computer image consists of pixels, the smallest addressable element. Each pixel has a position and a color. We can represent the color in different forms. A commonly used scheme for colored images is red-blue-green (RBG). If we reserve 24 bit for each pixel, i.e. 8 bit for each of the three colors, we can encode 256 different shades of red, blue, and green, respectively. Combining them, allows us to represent around 16 million different colors.

In order to access the image information from within our code, we can store the pixels in a two dimensional array, i.e. a matrix. While it would be possible to combine all three color channels inside a single coordinate of this matrix, it is more flexible to store only a single number. This leaves us with a matrix for each channel, so that we can represent grey-scale images as matrices and colored images as 3-dimensional tensors. The following figure illustrates how this process would look for a 3x3 pixel image. Note that in real images colors will be mixed most of the time.

![image pixels](https://thepracticaldev.s3.amazonaws.com/i/dfqan0qmy6ozmmb3d8f2.png)

Now let's take a look how CNNs work and how we can use this image representation as input for a CNN based classifier.

# Convolutional Neural Networks

## Architecture

CNNs can conceptually be divided into two parts: A *feature learning* part and a *classification* part. Each part consists of one or multiple layers. Feature learning is typically done by combining two types of layers: *Convolution layers* and *pooling* layers. Classification is then performed based on the learned features through *dense layers*, also known as fully connected layers. Additionally there is an *input layer*, containing the image data, as well as an *output layer*, containing the different classes we are trying to predict.

The following figure illustrates a CNN with one convolution layer, one pooling layer, and one dense layer. The task is to predict whether the image depicts a cat. Layers that are in-between the input and output layer are also referred to as *hidden layers* as there state is not directly visible when treating the model as a black box.

![cnn example](https://thepracticaldev.s3.amazonaws.com/i/lxmqa1f3uscmj3p5h8xv.png)

Considering a single color channel, the input layer can either be the raw image matrix or a preprocessed one, e.g. cropped, resized, with scaled color values between 0 and 1, and so on. The output layer represents the weights of each possible class that are assigned by the last hidden layer. In the next subsection we want to take a closer look at the different hidden layer types.

## Convolution Layers

A convolution layer is responsible for convolving a filter with the previous layer. If you are not familiar with 2-dimensional image filtering, you can take a look at the [Image Filtering](http://machinelearninguru.com/computer_vision/basics/convolution/image_convolution_1.html) post from [Machine Learning Guru](http://machinelearninguru.com/index.php). A filter can be viewed as a smaller image, i.e. a smaller matrix than the input, which is applied to a part of the input. If the part of the image matches what the filter expects, the output value will be high. Convolving the filter with the full input will yield another image that highlights certain aspects of the input.

Let's look at an example. The following figure shows the application of the Sobel-Feldman operator [sob], also known as the Sobel edge detector filter, to our blue cat. To be precise we are applying two filters, one for horizontal and one for vertical edges. We then combine both results to obtain an image showing both, horizontal and vertical edges. The filter kernels are depicted in the center of the figure.

![cat filter](https://thepracticaldev.s3.amazonaws.com/i/l1pxwr6c17040lk5j7ak.png)

There are different configuration options when defining a convolution layer. Each convolution layer can have one or multiple filters. The convolution layer will then output an intermediate representations of the input for each filter. The more filters, the more diverse our image features can become.

In addition to the number of filter kernels, we can select a *kernel size*. The kernel size determines the locality of the filter, i.e. how many of the surrounding pixels are being taken into account when applying the filter. Secondly, we need to pick a *stride* value. The stride determines how many pixels we advance when convolving. A stride of 1 will move the filter across every pixel, while a stride of 2 will skip every second pixel.

The question is how do we pick the filters we want to use? The answer is, we don't. The great thing about neural networks is that they learn the features themselves based on the training data. The training procedure will be discussed a bit more in a later section. Now let's move to the second type of feature learning layers: Pooling layers.

## Pooling Layers



## Dense Layers

## Training

- Backpropagation

# Handwritten Digit Recongition

https://immense-scrubland-99285.herokuapp.com/

## The Data

- Mnist

## The Front End

- Taken from http://www.williammalone.com/articles/create-html5-canvas-javascript-drawing-app/#demo-simple

![frontend 4](https://thepracticaldev.s3.amazonaws.com/i/ddx8hyz5ukzlk1a4koa7.png)

## The Back End

- Akka HTTP

## The Model

- Deeplearning4j

- CNN post: http://cs231n.github.io/convolutional-networks/

- use Rectified Linear Unit RELU activation as it has been found to speed up learning when used instead of sigmoids [img] [rnn]

Juutub https://www.youtube.com/watch?v=FmpDIaiMIeA

Convolution = repeating the filter (feature) across the whole image
Convolution layer = Convoluting all features => an image becomes a stack of filtered images
Add more layers: https://deeplearning4j.org/convolutionalnetwork

Tricks:

Stacking multiple layers:

Convolutional layer
Pooling (making the convoluted features a bit smaller)
Normalization (Rectified Linear Unit RELU) going through and making negative values 0

Output layer = fully connected layer?

Voting weights and features in convolution layers are learned using backpropagation.

```scala
/*
1 epoch Accuracy:        0.9258
2 epoch Accuracy:        0.9376
3 epoch Accuracy:        0.9490
*/
val conf = new NeuralNetConfiguration.Builder()
    .seed(123)
    .optimizationAlgo(OptimizationAlgorithm.STOCHASTIC_GRADIENT_DESCENT)
    .updater(new Nesterovs(0.006, 0.9))
    .l2(1e-4)
    .list
    .layer(
      0,
      new DenseLayer.Builder()
        .nIn(MnistLoader.height * MnistLoader.width)
        .nOut(100)
        .activation(Activation.RELU)
        .weightInit(WeightInit.XAVIER)
        .build
    )
    .layer(
      1,
      new OutputLayer.Builder(LossFunctions.LossFunction.NEGATIVELOGLIKELIHOOD)
        .nIn(100)
        .nOut(MnistLoader.nClasses)
        .activation(Activation.SOFTMAX)
        .weightInit(WeightInit.XAVIER)
        .build
    )
    .pretrain(false)
    .backprop(true)
    .setInputType(InputType.convolutional(MnistLoader.height, MnistLoader.width, MnistLoader.channels))
    .build
```

```scala
/*
1 epoch Accuracy:        0.9815
2 epoch Accuracy:        0.9843
3 epoch Accuracy:        0.9846
*/
val conf = new NeuralNetConfiguration.Builder()
    .seed(seed)
    .l2(0.0005)
    .weightInit(WeightInit.XAVIER)
    .optimizationAlgo(OptimizationAlgorithm.STOCHASTIC_GRADIENT_DESCENT)
    .updater(new Nesterovs(0.01, 0.9))
    .list()
    .layer(
      0,
      new ConvolutionLayer.Builder(5, 5)
        .nIn(MnistLoader.channels)
        .stride(1, 1)
        .nOut(20) // number of filters
        .activation(Activation.IDENTITY)
        .build()
    )
    .layer(
      1,
      new SubsamplingLayer.Builder(PoolingType.MAX)
        .kernelSize(2, 2)
        .stride(2, 2)
        .build()
    )
    .layer(
      2,
      new ConvolutionLayer.Builder(5, 5)
      //Note that nIn need not be specified in later layers
        .stride(1, 1)
        .nOut(50)
        .activation(Activation.IDENTITY)
        .build()
    )
    .layer(
      3,
      new SubsamplingLayer.Builder(PoolingType.MAX)
        .kernelSize(2, 2)
        .stride(2, 2)
        .build()
    )
    .layer(
      4,
      new DenseLayer.Builder()
        .activation(Activation.RELU)
        .nOut(500)
        .build()
    )
    .layer(
      5,
      new OutputLayer.Builder(LossFunctions.LossFunction.NEGATIVELOGLIKELIHOOD)
        .nOut(MnistLoader.nClasses)
        .activation(Activation.SOFTMAX)
        .build()
    )
    .setInputType(InputType.convolutional(MnistLoader.height, MnistLoader.width, MnistLoader.channels))
    .backprop(true)
    .pretrain(false)
    .build();
```

## Deployment with Heroku

- heroku uses `sbt compile stage` => https://github.com/FRosner/handwritten/commit/3b2f64c880a587d70432382d79f5330f47ed0837

- https://immense-scrubland-99285.herokuapp.com/

- `heroku login`
- `heroku create`
- `git push heroku master`
- `heroku open`

Because I am using the free tier, you might have to wait a bit if the app has not been used for a while.

## Problems

- No data no good results

- Model are regional (1 looks different in other countries, these numbers are US "standard")
![US 1](https://thepracticaldev.s3.amazonaws.com/i/4c0k7p6kogugsrs9mpje.png)

- poor performance if preprocessing not good (resizing, cropping, centering) => a high 7 looks like a 5

- use a more sophisticated model (maybe another layer)?

- UI does not support touch

# Summary

# References

- [sob] Sobel, I., Feldman, G., A 3x3 Isotropic Gradient Operator for Image Processing, presented at the Stanford Artificial Intelligence Project (SAIL) in 1968.
- [rnn] Deep Sparse Rectifier Neural Networks http://proceedings.mlr.press/v15/glorot11a/glorot11a.pdf
- [img] ImageNet Classification with Deep Convolutional Neural Networks http://www.cs.toronto.edu/~fritz/absps/imagenet.pdf
- [cnn] http://yann.lecun.com/exdb/publis/pdf/lecun-01a.pdf
- [mcd] Multi-column deep neural networks for image classification
