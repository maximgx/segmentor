import configparser as cp
import itertools as it
import pandas as pd
import numpy as np
import argparse
import timeit
import sys
import os
from multiprocessing import Pool
from functools import partial

from keras.preprocessing import sequence



PROC = 6

VAL_PROP = 0.2

def unpack_dataset(dataset):
    raw_dataset = pd.read_csv(dataset, delimiter = ";",
                                    skip_blank_lines = False)
    features = list(raw_dataset.columns.values)

    # get indexes of rows that are frames and not blank lines
    is_frame = raw_dataset.loc[:, features[0]].notnull()

    # give the same odd index to frames that are in the same utterance
    utterance_partition = (is_frame != is_frame.shift()).cumsum()

    # select frames from dataframe and group them by utterance,
    # the result is a set of dataframe per expression
    grouped_by_utterance = raw_dataset[is_frame].groupby(utterance_partition)

    # extract the maximum known length
    utterance_lengths = grouped_by_utterance.apply(len)
    max_utterance_length = np.max(utterance_lengths)

    keys = grouped_by_utterance.groups.keys()
    groups = [grouped_by_utterance.get_group(key) for key in keys]

    X = [group[features[0: -1]] for group in groups]
    Y = [group[features[-1]] for group in groups]

    return [X, Y, max_utterance_length]


def fill_with_zeros(X, Y, max_utterance_length):
    filled_X = []
    filled_Y = []

    # X is still a list of dataframes
    [filled_X.append(np.asarray(x)) for x in X]
    [filled_Y.append(np.asarray(y)) for y in Y]

    missing_features = np.zeros(len(X[0].columns.values))

    filled_X = sequence.pad_sequences(filled_X,
                            maxlen = max_utterance_length,
                            dtype = 'float',
                            padding = 'post',
                            truncating = 'post',
                            value = missing_features)
    filled_Y = sequence.pad_sequences(filled_Y,
                            maxlen = max_utterance_length,
                            dtype = 'float',
                            padding = 'post',
                            truncating = 'post',
                            value = 0.0)

    return [filled_X, filled_Y]



if __name__=="__main__":
    """
        The main purpose of this parallel labeling is to optimize time, so we don't
        care about memory usage here.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--trainset",
                        required = True,
                        help = "path to trainset .csv file")
    parser.add_argument("-v", "--static_validation",
                        required = True,
                        type = float,
                        choices = np.arange(.0, .4, .05),
                        help = "use static validation set shrinked from trainset")
    parser.add_argument("-s", "--testset",
                        required = True,
                        help = "path to testset .csv file")
    parser.add_argument("-c", "--cores",
                        type = int,
                        choices = range(1, 8),
                        help = "Number of physical core to use")
    args = parser.parse_args()


    if args.trainset and args.testset:
        phys_cores = PROC
        if args.cores:
            phys_cores = args.cores

        static_validation = VAL_PROP
        if args.static_validation:
            static_validation = args.static_validation


        pool = Pool(processes = phys_cores)
        start_time = timeit.default_timer()
        data = pool.map(unpack_dataset, [args.trainset, args.testset])
        elapsed_time = timeit.default_timer() - start_time
        print ("\nData unpacking performed in\t", elapsed_time, "seconds")


        max_utterance_length = max([length[2] for length in data])
        print ("Longest utterance has\t\t", max_utterance_length, "frames")

        train_X = []
        train_Y = []

        test_X = []
        test_Y = []

        start_time = timeit.default_timer()
        [[train_X, train_Y],
         [test_X, test_Y]] = pool.starmap(fill_with_zeros,
                                            zip([X[0] for X in data],
                                                [Y[1] for Y in data],
                                                it.repeat(max_utterance_length)))
        elapsed_time = timeit.default_timer() - start_time
        print ("Filled missing values in\t", elapsed_time, "seconds")

        print (train_X, np.shape(train_X))
        print (train_Y, np.shape(train_Y))
        # print (np.shape(filled_Y))

    else:
        parser.print_help()


"""
    https://github.com/fchollet/keras/issues/1711

    execute-timit.sh
        extract-corpus.sh
        prepare-dataset-parallel.py
        train-model.py
            blstm.py
            convolution.py

"""