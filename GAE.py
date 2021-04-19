# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-
# Author : Ali Mirzaei
# Date : 19/09/2017

import glob
from keras.models import Sequential, Model
from keras.layers import Dense, Input, Flatten, Reshape
from keras.datasets import mnist, cifar10
from keras.optimizers import Adam
import numpy as np
import matplotlib.pyplot as plt
from sklearn.neighbors import KernelDensity
from mpl_toolkits.mplot3d import Axes3D
import helpers
from sklearn.model_selection import GridSearchCV
import keras
from keras.initializers import RandomNormal

initializer = RandomNormal(mean=0.0, stddev=0.01, seed=None)

class GAE():
    def __init__(self, img_shape=(28, 28), encoded_dim=2):
        self.encoded_dim = encoded_dim
        self.optimizer = Adam(0.001)
        self.optimizer_discriminator = Adam(0.00001)
        self._initAndCompileFullModel(img_shape, encoded_dim)
        self.img_shape = img_shape

    def _genEncoderModel(self, img_shape, encoded_dim):
        """ Build Encoder Model Based on Paper Configuration
        Args:
            img_shape (tuple) : shape of input image
            encoded_dim (int) : number of latent variables
        Return:
            A sequential keras model
        """
        encoder = Sequential()
        encoder.add(Flatten(input_shape=img_shape))
        encoder.add(Dense(1000, activation='relu'))
        encoder.add(Dense(1000, activation='relu'))
        encoder.add(Dense(encoded_dim))
        encoder.summary()
        return encoder

    def _getDecoderModel(self, encoded_dim, img_shape):
        """ Build Decoder Model Based on Paper Configuration
        Args:
            encoded_dim (int) : number of latent variables
            img_shape (tuple) : shape of target images
        Return:
            A sequential keras model
        """
        decoder = Sequential()
        decoder.add(Dense(1000, activation='relu', input_dim=encoded_dim))
        decoder.add(Dense(1000, activation='relu'))
        decoder.add(Dense(np.prod(img_shape), activation='sigmoid'))
        decoder.add(Reshape(img_shape))
        decoder.summary()
        return decoder

    def _getDescriminator(self, img_shape):
        """ Build Descriminator Model Based on Paper Configuration
        Args:
            encoded_dim (int) : number of latent variables
        Return:
            A sequential keras model
        """
        discriminator = Sequential()
        discriminator.add(Flatten(input_shape=img_shape))
        discriminator.add(Dense(1000, activation='relu',
                                kernel_initializer=initializer,
                bias_initializer=initializer))
        discriminator.add(Dense(1000, activation='relu', kernel_initializer=initializer,
                bias_initializer=initializer))
        discriminator.add(Dense(1, activation='sigmoid', kernel_initializer=initializer,
                bias_initializer=initializer))
        discriminator.summary()
        return discriminator

    def _initAndCompileFullModel(self, img_shape, encoded_dim):
        self.encoder = self._genEncoderModel(img_shape, encoded_dim)
        self.decoder = self._getDecoderModel(encoded_dim, img_shape)
        self.discriminator = self._getDescriminator(img_shape)
        img = Input(shape=img_shape)
        encoded_repr = self.encoder(img)
        gen_img = self.decoder(encoded_repr)
        self.autoencoder = Model(img, gen_img)
        self.autoencoder.compile(optimizer=self.optimizer, loss='mse')
        self.discriminator.compile(optimizer=self.optimizer, 
                                   loss='binary_crossentropy',
                                   metrics=['accuracy'])
        for layer in self.discriminator.layers:
            layer.trainable = False
        
        latent = Input(shape=(encoded_dim,))
        gen_image_from_latent = self.decoder(latent)
        is_real = self.discriminator(gen_image_from_latent)
        self.decoder_discriminator = Model(latent, is_real)
        self.decoder_discriminator.compile(optimizer=self.optimizer_discriminator, loss='binary_crossentropy',
                                           metrics=['accuracy'])

    def imagegrid(self, epochnumber):
        fig = plt.figure(figsize=[20, 20])
        for i in range(-5, 5):
            for j in range(-5,5):
                topred = np.array((i*0.5,j*0.5))
                topred = topred.reshape((1, 2))
                img = self.decoder.predict(topred)
                img = img.reshape(self.img_shape)
                ax = fig.add_subplot(10, 10, (i+5)*10+j+5+1)
                ax.set_axis_off()
                ax.imshow(img, cmap="gray")
        fig.savefig(str(epochnumber)+".png")
        plt.show()
        plt.close(fig)

    def train(self, x_train, batch_size=32, epochs=5):
        fileNames = glob.glob('models/GAE/weights_mnist_autoencoder.*')
        fileNames.sort()
        if(len(fileNames) != 0):
            savedEpoch = int(fileNames[-1].split('.')[1])
            self.autoencoder.load_weights(fileNames[-1])
        else:
            savedEpoch=-1
        if(savedEpoch<epochs-1):
            self.autoencoder.fit(x_train, x_train, batch_size=batch_size,
                                 epochs=epochs, 
                                 callbacks=[keras.callbacks.ModelCheckpoint('models/GAE/weights_autoencoder.{epoch:02d}.hdf5', 
                                                                           verbose=0, 
                                                                           save_best_only=False, 
                                                                           save_weights_only=False, 
                                                                           mode='auto', 
                                                                           period=1)])
        print("Training KDE")
        codes = self.encoder.predict(x_train)
#        params = {'bandwidth': [3.16]}#np.logspace(0, 2, 5)}
#        grid = GridSearchCV(KernelDensity(), params, n_jobs=4)
#        grid.fit(codes)
#        print grid.best_params_
#        self.kde = grid.best_estimator_
        self.kde = KernelDensity(kernel='gaussian', bandwidth=3.16).fit(codes)
        print("Initial Training of discriminator")
        fileNames = glob.glob('models/GAE/weights_mnist_discriminator.*')
        fileNames.sort()
        if(len(fileNames) != 0):
            savedEpoch = int(fileNames[-1].split('.')[1])
            self.discriminator.load_weights(fileNames[-1])
        else:
            savedEpoch = -1
        if(savedEpoch<epochs-1):
            imgs_fake = self.generate(n = len(x_train))
            #gen_imgs = self.decoder.predict(latent_fake)
            valid = np.ones((len(x_train), 1))
            fake = np.zeros((len(x_train), 1))
            labels = np.vstack([valid, fake])
            images = np.vstack([x_train, imgs_fake])
            # Train the discriminator
            self.discriminator.fit(images, labels, epochs=epochs, batch_size=batch_size, shuffle=True, 
                                   callbacks=[keras.callbacks.ModelCheckpoint('models/GAE/weights_discriminator.{epoch:02d}.hdf5', 
                                                                               verbose=0, 
                                                                               save_best_only=False, 
                                                                               save_weights_only=False, 
                                                                               mode='auto', 
                                                                               period=1)])

        print("Training GAN")
        self.generateAndPlot(x_train, fileName="before_gan.png")
        self.trainGAN(x_train, epochs=len(x_train)/batch_size, batch_size= batch_size)
        self.generateAndPlot(x_train, fileName="after_gan.png")
    def trainGAN(self, x_train, epochs =1000, batch_size=32):
        half_batch = batch_size/2
        for epoch in range(epochs):
            #---------------Train Discriminator -------------
            # Select a random half batch of images
            idx = np.random.randint(0, x_train.shape[0], half_batch)
            imgs_real = x_train[idx]
            # Generate a half batch of new images
            imgs_fake = self.generate(n = half_batch)
            #gen_imgs = self.decoder.predict(latent_fake)
            valid = np.ones((half_batch, 1))
            fake = np.zeros((half_batch, 1))
            # Train the discriminator
            d_loss_real = self.discriminator.train_on_batch(imgs_real, valid)
            d_loss_fake = self.discriminator.train_on_batch(imgs_fake, fake)
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)
            #d_loss = (0,0)
            codes = self.kde.sample(batch_size)
            # Generator wants the discriminator to label the generated representations as valid
            valid_y = np.ones((batch_size, 1))
            # Train generator
            g_logg_similarity = self.decoder_discriminator.train_on_batch(codes, valid_y)
            # Plot the progress
            print ("%d [D accuracy: %.2f] [G accuracy: %.2f]" % (epoch, d_loss[1], g_logg_similarity[1]))
#            if(epoch % save_interval == 0):
#                self.imagegrid(epoch)

    def generate(self, n = 10000):
        codes = self.kde.sample(n)
        images = self.decoder.predict(codes)
        return images

    def generateAndPlot(self, x_train, n = 10, fileName="generated.png"):
        fig = plt.figure(figsize=[20, 20])
        images = self.generate(n*n)
        index = 1
        for image in images:
            image = image.reshape(self.img_shape)
            ax = fig.add_subplot(n, n+1, index)
            index=index+1
            ax.set_axis_off()
            ax.imshow(image, cmap="gray")
            if((index)%(n+1) == 0):
                nearest = helpers.findNearest(x_train, image)
                ax = fig.add_subplot(n, n+1, index)
                index= index+1
                ax.imshow(nearest, cmap="gray")
        fig.savefig(fileName)
        plt.show()

    def meanLogLikelihood(self, x_test):
        KernelDensity(kernel='gaussian', bandwidth=0.2).fit(codes)
if __name__ == '__main__':
    # Load MNIST dataset
    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    x_train = x_train.astype(np.float32) / 255.
    x_test = x_test.astype(np.float32) / 255.
    ann = GAE(img_shape=(28,28), encoded_dim=2)
    ann.train(x_train, epochs=1)
    ann.generateAndPlot(x_train)
#    generated = ann.generate(10000)
#    L = helpers.approximateLogLiklihood(generated, x_test, searchSpace=[.1])
#    print L
#    #codes = ann.kde.sample(1000)
#    #ax = Axes3D(plt.gcf())
#    codes = ann.encoder.predict(x_train)
#    plt.scatter(codes[:,0], codes[:,1], c=y_train)
#    plt.show()
