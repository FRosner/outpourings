---
title: Handwritten Digit Recognition Using Convolutional Neural Networks
published: true
description: Convolutional neural networks are a powerful type of models for image classification. In this blog post we want to look at the "Hello World" application of image classification - Handwritten digits.
tags: showdev, deeplearning, scala, javascript
cover_image: https://thepracticaldev.s3.amazonaws.com/i/3soqhs8850b2h7klkqia.png
---

# Introduction

In this blog post I want to share a small application I developed that classifies images of hand written digits, together with the lessons learned while developing it. When it comes to machine learning, in the past I have mainly worked with text data. Pattern recognition on image data is new to me but I think it is a very useful skill.

The post is structured as follows. First we are introducing the concept of image classification and what makes it special compared to other problems such as text classification. The next section introduces a machine learning model called Convolutional Neural Network (CNN), which is commonly used in image classification. The third section show cases an example application which performs handwritten digit classification through a web interface. We are closing the post by summarizing the main findings and ideas.

The application is written in Scala, HTML, CSS, and JavaScript. However the concepts can be transferred to other languages as well. I am also trying to keep the mathematical details to a minimum, focusing on the necessary information for the reader to develop an intuition about the algorithms used. In case you are interested in getting a deeper understanding of the subject, I recommend to take a look at other tutorials, research papers or books.

# Image Classification

Machine learning algorithms expect data to be represented in some numerical format that the computer can understand. When using probabilistic models, e.g., your data has to fit into the format expected by the distributions your model is using.

As an example consider a multinomial mixture model [1]. To utilize this type of model, you need to be able to convert your data into counts. In text this can be achieved by introducing a counting variable for each possible word of each cluster in each possible document. This model is very simple and works great for many use cases. However it has one big disadvantage: It discards a lot of information, e.g. term cooccurrences and position within the document.

For image data this problem is even greater. While you can still determine whether an email is spam by just looking at the word counts, recognizing images with cats is much harder when only counting the number of pixels having a specific color. While text data is 1-dimensional, i.e. a sequence of terms, images are at least 2-dimensional, i.e. a matrix of pixels, and contain a lot more information in the spatial relation of the pixels.

Luckily there are other models we can use that take spacial information into account. A very commonly used type of models are [Convolutional Neural Networks](http://cs231n.github.io/convolutional-networks/) (CNN). While research in this area is ongoing for some time now [2], the era of GPU based training lead to major break-throughs in terms of model performance in the recent years [3].

How do we represent a raw image in the computer? The smallest addressable element of a computer image is a *pixel*. Each pixel has a position and a color. We can represent the color in different forms. A commonly used scheme for colored images is red-blue-green (RBG). If we reserve 24 bit for each pixel, i.e. 8 bit for each of the three colors, we can encode 256 different shades of red, blue, and green, respectively. Combining them, allows us to represent around 16 million different colors.

In order to access the image information from within our code, we can store the pixels in a two dimensional array, i.e. a matrix. While it would be possible to combine all three color channels inside a single coordinate of this matrix, it is more efficient to store only a single number. This leaves us with a matrix for each channel, so that we can represent grey-scale images as matrices and colored images as 3-dimensional tensors. The following figure illustrates how this process would look for a 3×3 pixel image. Note that in real images colors will be mixed most of the time.

![image pixels](https://thepracticaldev.s3.amazonaws.com/i/dfqan0qmy6ozmmb3d8f2.png)

Now let's take a look how CNNs work and how we can use this image representation as input for a CNN based classifier.

# Convolutional Neural Networks

## Architecture

A neural network is a machine learning model which consists of connected layers of *neurons*. A neuron contains a number, the so called *activation*. Connections are assigned *weights*, which describes the strength of the signal to the connected neuron.

Input data is fed into the first layer, activating each input neuron to some extend. Based on the weights and an *activation function* the network determines which neurons from the next layer to activate and how strong the activation is going to be. This so called *feedforward* process is continued until the output neurons are activated. The architecture of a neural network has a huge influence on which data it can work with and its performance. The following figure illustrates a simple neural network with three layers.

![simple nn](https://thepracticaldev.s3.amazonaws.com/i/7j7lzvnj9impxg32vsbt.png)

CNNs are a special type of neural networks. They can be divided into two parts: A *feature learning* part and a *classification* part. Each part consists of one or multiple layers. Feature learning is typically done by combining two types of layers: *Convolution layers* and *pooling* layers. Classification is then performed based on the learned features through *dense layers*, also known as fully connected layers. Additionally there is an *input layer*, containing the image data, as well as an *output layer*, containing the different classes we are trying to predict.

The following figure illustrates a CNN with one convolution layer, one pooling layer, and one dense layer. The task is to predict whether the image depicts a cat. Layers that are in-between the input and output layer are also referred to as *hidden layers* as there state is not directly visible when treating the model as a black box.

![cnn example](https://thepracticaldev.s3.amazonaws.com/i/lxmqa1f3uscmj3p5h8xv.png)

Considering a single color channel, the input layer can either be the raw image matrix or a preprocessed one, e.g. cropped, resized, with scaled color values between 0 and 1, and so on. The output layer represents the weights of each possible class that are assigned by the last hidden layer. In the next subsection we want to take a closer look at the different hidden layer types.

## Convolution Layers

A convolution layer is responsible for convolving a filter with the previous layer. If you are not familiar with 2-dimensional image filtering, you can take a look at the [Image Filtering](http://machinelearninguru.com/computer_vision/basics/convolution/image_convolution_1.html) post from [Machine Learning Guru](http://machinelearninguru.com/index.php). A filter can be viewed as a smaller image, i.e. a smaller matrix than the input, which is applied to a part of the input. If the part of the image matches what the filter expects, the output value will be high. Convolving the filter with the full input will yield another image that highlights certain aspects of the input.

Let's look at an example. The following figure shows the application of the Sobel-Feldman operator [4], also known as the Sobel edge detector filter, to our blue cat. To be precise we are applying two filters, one for horizontal and one for vertical edges. We then combine both results to obtain an image showing both, horizontal and vertical edges. The filter kernels are depicted in the center of the figure.

![cat filter](https://thepracticaldev.s3.amazonaws.com/i/l1pxwr6c17040lk5j7ak.png)

There are different configuration options when defining a convolution layer. Each convolution layer can have one or multiple filters. The convolution layer will then output an intermediate representations of the input for each filter. The more filters, the more diverse our image features can become.

In addition to the number of filter kernels, we can select a *kernel size*. The kernel size determines the locality of the filter, i.e. how many of the surrounding pixels are being taken into account when applying the filter. Secondly, we need to pick a *stride* value. The stride determines how many pixels we advance when convolving. A stride of 1 will move the filter across every pixel, while a stride of 2 will skip every second pixel.

The question is how do we pick the filters we want to use? The answer is, we don't. The great thing about neural networks is that they learn the features themselves based on the training data. The training procedure will be discussed a bit more in a later section. Now let's move to the second type of feature learning layers: Pooling layers.

## Pooling Layers

Pooling layers are applied to down-sample the input. The goal is to reduce the computational complexity of the model and to avoid overfitting. The information loss is usually not that problematic as the exact location of the features is less important than the relation between them.

Pooling is implemented by applying a special filter function while choosing the kernel size and stride value in a way that the filter applications do not overlap. A commonly used technique is called *max pooling*. In max pooling we select the maximum value of the sub-region for our sub-sampled output. In the next figure we can see the result of applying 2×2 max-pooling to a 4×4 input matrix.

![2x2 max pooling](https://thepracticaldev.s3.amazonaws.com/i/tl5e7lypd3dsbyf61g1o.png)

The following figure depicts the result of sub-sampling the output of the convolution layer twice. Note that sub-sampling reduces the image size, but I scaled the size up again to visualize the loss of information.

![subsampled cat](https://thepracticaldev.s3.amazonaws.com/i/y73knocyw02zehm9cu5b.png)

How can we use the derived features to predict a class? Let's find out by looking closer into how dense layers work.

## Dense Layers

Dense layers connect every neuron from the previous layer to the next one. In the context of CNNs they form the classification part of the network. Neurons in the dense layers learn which features each class is composed of.

Dense layers are more complex in terms of parameter fitting than convolution layers. A filter with a 3×3 kernel from a convolution layer has 9 parameters independent of the number of input neurons. A fully connected layer of 16 neurons with 28×28 neurons on the previous layer already has 28×28×16 = 12,544 weights.

Now that we are more familiar with the different components of CNNs, you might wonder how to find the correct values for all parameters, i.e. the filter kernels and weights in the dense layers.

## Training

Like all machine learning algorithms, training is done based on example inputs where the class label is known. An untrained CNN is initialized with random parameters. We can then feed training examples through the network and inspect the activation of the output neurons. Based on the expected activation, i.e. full activation of the neuron associated with the correct class and no activation of the rest, we can derive a cost function which captures how wrong the network was.

Then we can start to tune the parameters to reduce the cost. This is done starting from the output neurons, adjusting the parameters of each layer up to the input layer. This learning process is refered to as *backpropagation*. How do we know which parameter to increase and which to decrease, and how much?

I'm not going to go into too much mathematical detail here but you might remember from calculus that for some functions you can compute a derivative, telling you how the output of the function changes given a change in the input variable. The derivative represents the slope of the tangent of the function when plotted. If we computed this for our cost function it would tell us how each parameter influences the outcome towards our expected class label.

As our cost function has not only one but potentially thousands of input variables, (recall the number of weights already for a small dense layer), we can utilize the so called *gradient*. The gradient is a generalization of the derivative for multi-variable functions. To be precise we want to use the negative gradient, as we aim at reducing the cost. The negative gradient will tell us how we need to adjust the network parameters to better classify the training examples. This method is called *gradient descent*.

Computing the exact negative gradient for all our training examples is computationally infeasible most of the time. However, we can use a small trick: The input data is shuffled and grouped into small batches. We then compute the gradient only on this small subset, adjust the parameters of the network accordingly, and continue with the next batch. This so called *stochastic gradient descent* gives a good-enough approximation of the exact answer.

Keep in mind however that by descending the gradient we can only improve as much as the initial random parameters allow us. The network might not be able to improve without starting with completely different weights, getting stuck in a so called *local minimum* of the cost function. Several techniques exist to avoid getting stuck in a local minimum but they also have their disadvantages.

Now that we have our trained model we can feed images without a label and look at the output to determine the correct class. Next let's look at the "Hello World" example of image classification and the small app I built based on it.

# Handwritten Digit Recongition

## The Data

The "Hello World" of image classification is a seemingly simple, yet non-trivial problem of classifying handwritten digits. There is a rich training and test dataset is available online for free within the Modified National Institute of Standards and Technology database, widely known as [MNIST database](http://yann.lecun.com/exdb/mnist/).

Each digit is available as a 28×28 pixel grey scale image. The following picture shows a few example images for each digit.

![mnist](https://thepracticaldev.s3.amazonaws.com/i/6sm156embzylvs2h41vp.png)

## Application Architecture

In order to build something that one can use and play around with, my goal was to build a web application that allows you to draw a digit and get it classified. I am using [Deeplearning4j](https://deeplearning4j.org/) (DL4J) to build, train, validate, and apply the model. It is an open source deep learning library for the JVM. Please find a small architecture diagram below.

![application architecture](https://thepracticaldev.s3.amazonaws.com/i/h368re5hbwf5sqnho0if.png)

The application is split into two parts:

- Training & Validation
- Prediction

The training and validation happens offline. It reads the data from a directory structure which already splits the data into training and test data, as well as containing the individual digits in their respective directories. After training is successful, the network gets serialized and persisted on the filesystem (`model.zip`). The prediction API then loads the model on startup and uses it to serve incoming requests from the front end.

Before we are looking a bit into the individual components in detail, please note that the [source code](https://github.com/FRosner/handwritten) is available on GitHub and the app is [online](https://immense-scrubland-99285.herokuapp.com/) and can be tried out thanks to [Heroku](https://www.heroku.com/). I am only using a free tier so you might have to wait a bit when the application is used for the first time after a while as it lazily starts the server.

## The Front End

The front end is a simple HTML 5 canvas plus a bit of JavaScript to send the data to the back end. It is heavily inspired by the [Create a Drawing App with HTML 5 Canvas and JavaScript](http://www.williammalone.com/articles/create-html5-canvas-javascript-drawing-app/#demo-simple) tutorial by [William Malone](http://www.williammalone.com/about/). In case you cannot access the [live version](https://immense-scrubland-99285.herokuapp.com/) right now, you can check out a screen shot of the front end below.

![frontend 4](https://thepracticaldev.s3.amazonaws.com/i/ddx8hyz5ukzlk1a4koa7.png)

It features a drawing canvas, a button to send the canvas content to the back end, a button to clear the canvas, and an output area for the classification result. The [`index.html`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/resources/static/index.html) is not very complicated. Here are the HTML elements used:

```html
<body>
    <div id="canvasDiv"></div>
    <div id="controls">
        <button id="predictButton" type="button">Predict</button>
        <button id="clearCanvasButton" type="button">Clear</button>
    </div>
    <div id="predictionResult">
    </div>
</body>
```

We then add some CSS ([`app.css`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/resources/static/app.css)) to the mix to make it look less ugly. The JavaScript code ([`app.js`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/resources/static/app.js)) is basic [jQuery](https://jquery.com/), nothing fancy and very prototypical. It first builds up the canvas and defines the drawing functions. Prediction is done by sending the canvas content to the back end. Once the result arrives we are showing it in the output `div`.

```javascript
$('#predictButton').mousedown(function(e) {
  canvas.toBlob(function(d) {
  var fd = new FormData();
  fd.append('image', d)
    $.ajax({
      type: "POST",
      url: "predict",
      data: fd,
      contentType: false,
      processData: false
    }).done(function(o) {
      $('#predictionResult').text(o)
    });
  });
});
```

## The Back End

The back end ([`PredictAPI.scala`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/scala/de/frosner/PredictAPI.scala)) is a small [Akka HTTP](https://doc.akka.io/docs/akka-http/current/) web server. On startup we load the model from disk. We have to wrap the access in a [synchronized block](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/scala/de/frosner/SynchronizedClassifier.scala#L9), as the default model implementation of DL4J is not thread safe.

```scala
val model = new SynchronizedClassifier(
  ModelSerializer.restoreMultiLayerNetwork("model.zip")
)
```

There is a route for the static files, i.e. `index.html`, `app.js`, and `app.css`, as well as one for receiving images of digits for prediction.

```scala
val route =
  path("") {
    getFromResource("static/index.html")
  } ~
  pathPrefix("static") {
    getFromResourceDirectory("static")
  } ~
  path("predict") {
    fileUpload("image") {
      case (fileInfo, fileStream) =>
        val in = fileStream.runWith(StreamConverters.asInputStream(3.seconds))
        val img = invert(MnistLoader.fromStream(in))
        complete(model.predict(img).toString)
    }
  }
```

For every incoming image we have to apply some basic transformations like resizing and scaling, which are implemented in the [`MnistLoad.fromStream`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/scala/de/frosner/MnistLoader.scala#L51) method. We are also inverting the image as the network is trained to classify white digits on black background.

## The Model

The model used is a seven layer CNN, heavily inspired by the [DL4J Code Example](https://deeplearning4j.org/convolutionalnetwork) for CNNs. The hidden layers are two pairs of convolution-pooling layers, as well as one dense layer. It is trained using stochastic gradient descent with batches of 64 images. The test accuracy of the model is 98%.

The training and validation process is implemented in [`TrainMain.scala`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/src/main/scala/de/frosner/TrainMain.scala). There you can also find the exact model configuration. I don't want to go into too much detail at this point but if you have any questions regarding the model architecture, feel free to drop a comment.

## Deployment with Heroku

I chose to deploy the application with Heroku as it allows to quickly deploy applications publicly, has a free tier, and integrated very well within the development workflow. I am using the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli).

For Scala projects built with SBT, Heroku will execute `sbt stage`. This will produce a binary artifact of the app together with all library dependencies. The [`Procfile`](https://github.com/FRosner/handwritten/blob/2c40da1526fa312d603b0a5c74b35c79d7407818/Procfile) specifies how to start the app. Here are the commands required to deploy to Heroku.

- `heroku login` (logging in to your Heroku account)
- `heroku create` (initializing the `heroku` remote)
- `git push heroku master` (push changes, triggering a build)
- `heroku open` (open the application URL in your browser)

## Problems

If you tried the application you might have run into some weird output. In fact, there are multiple issues which might lead to misclassification of your drawn digit even though the model has 98% accuracy.

One factor is that the images are not centered. Although the combination of convolution layers and subsampling through pooling helps, I suspect that moving and resizing all digits to the center of the canvas would aid the performance. For optimal results, try drawing the image in the lower 2/3 of the canvas.

Additionally, the training data captures a certain style of hand writing common in the US. While in other parts of the world, the digit 1 consists of multiple lines, in the US people often write it as one line. This can lead to a 1, written differently, being classified as a 7. The following figure illustrates this.

![US 1](https://thepracticaldev.s3.amazonaws.com/i/4c0k7p6kogugsrs9mpje.png)

# Summary

In this post we have seen how CNNs can be used to classify image data. Using a combination of approximate optimization techniques, sub-sampling and filter application we are able to train a deep network that captures features of the input images well.

Using a bit of JavaScript, HTML and CSS you are able to develop a front end for drawing images to be classified. The back end can be implemented using an HTTP server like Akka HTTP in combination with a deep learning framework like DL4J.

We have also seen that the classification performance in the real world only matches the test accuracy if the real data corresponds to the training and test data used when building the model. It is crucial to monitor model performance during run time, adjusting or retraining the model periodically to keep the accuracy high.

# References

- [1] Rigouste, L., Cappé, O. and Yvon, F., 2007. Inference and evaluation of the multinomial mixture model for text clustering. Information processing & management, 43(5), pp.1260-1280.
- [2] LeCun, Y., Bottou, L., Bengio, Y. and Haffner, P., 1998. Gradient-based learning applied to document recognition. Proceedings of the IEEE, 86(11), pp.2278-2324.
- [3] Ciregan, D., Meier, U. and Schmidhuber, J., 2012, June. Multi-column deep neural networks for image classification. In Computer vision and pattern recognition (CVPR), 2012 IEEE conference on (pp. 3642-3649). IEEE.
- [4] Sobel, I., Feldman, G., A 3x3 Isotropic Gradient Operator for Image Processing, presented at the Stanford Artificial Intelligence Project (SAIL) in 1968.
