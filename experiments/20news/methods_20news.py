import ssnmf
from ssnmf.evaluation  import Evaluation
import numpy as np
import pandas as pd
from utils_20news import *
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.decomposition import NMF
from scipy.optimize import nnls as nnls
from sklearn import metrics
import pickle
from statistics import mean
from statistics import median
from statistics import stdev

class Methods:

    def __init__(self, X_train, X_val, X_test, train_labels, val_labels, test_labels, X_train_full,\
                    train_labels_full, cls_names, feature_names_train):
        """
        Class for all methods.

        Parameters:
            X_train (ndarray): tfidf train data matrix, shape (vocabulary size, number of train documents)
            X_val (ndarray): tfidf validation data matrix, shape (vocabulary size, number of val documents)
            X_test (ndarray): tfidf test data matrix, shape (vocabulary size, number of test documents)
            train_labels (ndarray): labels of all documents in train set
            val_labels (ndarray):  labels of all documents in val set
            test_labels (ndarray):  labels of all documents in test set
            X_train_full (ndarray): tfidf full train data matrix, shape (vocabulary size, number of full train documents)
            train_labels_full (ndarray):  labels of all documents in full train set
            cls_names (list): list of all class names (used for plotting)
            feature_names_train (list): list of features of the trained tfidf vectorizer (used for printing keywords)

        """
        self.X_train = X_train
        self.X_val = X_val
        self.X_test = X_test
        self.train_labels = train_labels
        self.test_labels = test_labels
        self.val_labels = val_labels
        self.X_train_full = X_train_full
        self.train_labels_full = train_labels_full
        self.cls_names = cls_names
        self.feature_names_train = feature_names_train

        # One-hot encode labels
        train_onehot_labels = pd.get_dummies(self.train_labels)
        self.y_train = train_onehot_labels.T.to_numpy()
        test_onehot_labels = pd.get_dummies(self.test_labels)
        self.y_test = test_onehot_labels.T.to_numpy()
        val_onehot_labels = pd.get_dummies(self.val_labels)
        self.y_val = val_onehot_labels.T.to_numpy()
        train_full_onehot_labels = pd.get_dummies(self.train_labels_full)
        self.y_train_full = train_full_onehot_labels.T.to_numpy()

    def MultinomialNB(self, print_results=0):
        """
        Run Multinomial Naive Bayes on the TFIDF representation of documents.

        Args:
            print_results (boolean): 1: print classification report, heatmaps, and features, 0:otherwise
        Retruns:
            nb_acc (float): classification accuracy on test set
            nb_predicted (ndarray): predicted labels for data points in test set
        """

        print("\nRunning Multinomial Naive Bayes.")
        nb_clf = MultinomialNB().fit(self.X_train_full.T, self.train_labels_full)
        nb_predicted = nb_clf.predict(self.X_test.T)
        nb_acc = np.mean(nb_predicted == self.test_labels)

        print(f"The classification accuracy on the test data is {nb_acc*100:.4f}%\n")

        if print_results == 1:
            # Extract features
            top_features(nb_clf, self.feature_names_train, self.cls_names, top_num = 10)
            print(metrics.classification_report(self.test_labels, nb_predicted, target_names=self.cls_names))

        return nb_acc, nb_predicted

    def SVM(self, print_results=0):
        """
        Run SVM on the TFIDF representation of documents.

        Args:
            print_results (boolean): 1: print classification report, heatmaps, and features, 0:otherwise
        Retruns:
            svm_acc (float): classification accuracy on test set
            svm_predicted (ndarray): predicted labels for data points in test set
        """

        print("\nRunning SVM.")
        svm_clf = Pipeline([('scl',StandardScaler()), \
                    ('clf', SGDClassifier())])
        svm_clf.fit(self.X_train_full.T, self.train_labels_full)
        svm_predicted = svm_clf.predict(self.X_test.T)
        svm_acc = np.mean(svm_predicted == self.test_labels)
        print(f"The classification accuracy on the test data is {svm_acc*100:.4f}%\n")

        if print_results == 1:
            # Extract features
            top_features(svm_clf['clf'], self.feature_names_train, self.cls_names, top_num = 10)
            print(metrics.classification_report(self.test_labels, svm_predicted, target_names=self.cls_names))

        return svm_acc, svm_predicted

    def NMF(self, rank, nmf_tol, print_results=0):
        """
        Run NMF on the TFIDF representation of documents to obtain a low-dimensional representaion (dim=rank),
        then apply SVM to classify the data.

        Args:
            rank (int): input rank for NMF
            nmf_tol (float): tolerance for termanating NMF model
            print_results (boolean): 1: print classification report, heatmaps, and keywords, 0:otherwise
        Retruns:
             nmf_svm_acc (float): classification accuracy on test set
             W (ndarray): learnt word dictionary matrix, shape (words, topics)
             nn_svm (ndarray): learnt (nonegative) coefficient matrix for SVM classification, shape (classes, topics)
             nmf_svm_predicted (ndarray): predicted labels for data points in test set
             nmf_iter (int): actual number of iterations of NMF
             H (ndarray): document representation matrix for train set, shape (topics, train documents)
             H_test (ndarray): document representation matrix for test set, shape (topics, test documents)
        """
        self.nmf_tol = nmf_tol

        print("\nRunning NMF + SVM")
        nmf = NMF(n_components=rank, init= 'random', tol = self.nmf_tol, solver = 'mu', max_iter = 400)

        # TRAINING STEP
        # Dictionary matrix, shape (vocabulary, topics)
        W = nmf.fit_transform(self.X_train_full)
        # Representation matrix, shape (topics, documents)
        H = nmf.components_
        # Actual number of iterations
        nmf_iter = nmf.n_iter_
        # Train SVM classifier on train data
        text_clf = Pipeline([('scl',StandardScaler()), \
                                ('clf', SGDClassifier(tol=1e-5))])
        text_clf.fit(H.T, self.train_labels_full)

        # TESTING STEP
        # Compute the representation of test data
        H_test = np.zeros([rank, np.shape(self.X_test)[1]])
        for i in range(np.shape(self.X_test)[1]):
            H_test[:,i] = nnls(W, self.X_test[:,i])[0]
        # Classify test data using trained SVM classifier
        nmf_svm_predicted = text_clf.predict(H_test.T)
        # Report classification accuracy on test data
        nmf_svm_acc = np.mean(nmf_svm_predicted == self.test_labels)
        print(f"The classification accuracy on the test data is {nmf_svm_acc*100:.4f}%\n")

        # SVM non-negaitve coefficient matrix
        nn_svm = text_clf['clf'].coef_.copy()
        nn_svm[nn_svm<0] = 0

        if print_results == 1:
            # Extract top keywords representaion of topics
            print_keywords(W.T, features=self.feature_names_train, top_num=10)
            print(metrics.classification_report(self.test_labels, nmf_svm_predicted, target_names=self.cls_names))
            factors_heatmaps(nn_svm, cls_names=self.cls_names)

        return nmf_svm_acc, W, nn_svm, nmf_svm_predicted, nmf_iter, H, H_test


    def SSNMF(self, modelNum, ssnmf_tol, lamb, ka, itas, hyp_search = 0, print_results=0):
        """
        Run (S)SNMF on the TFIDF representation of documents.

        Args:
            modelNum (int): SSNMF model number
            ssnmf_tol (float): tolerance for termanating SSNMF model
            lamb (float): regularization parameter of SSNMF
            ka (int): input rank for SSNMF
            itas (int): maximum number of multiplicative update iterations
            hyp_search (boolean): 0: run hyperparameter search algorithm, 1:otherwise
            print_results (boolean): 1: print classification report, heatmaps, and keywords, 0:otherwise
        Retruns:
            test_evals(list): [float(total reconstruction error (model objective function) on test data),
                                    float(data reconstruction error on test data),
                                    float(label reconstruction error on test data),
                                    float(classification accuracy on test data)]
            eval_module.model.A (ndarray): learnt word dictionary matrix for data reconstruction, shape (words, topics)
            eval_module.model.B (ndarray): learnt dictionary matrix for classification, shape (classes, topics)
            ssnmf_predicted (ndarray): predicted labels for data points in test set
            ssnmf_iter (int): actual number of iterations of SSNMF model
            S (ndarray): document representation matrix for train set, shape (topics, train + test documents)
            S_test (ndarray): document representation matrix for test set, shape (topics, test documents)
        """

        print(f"\nRunning SSNMF for Model {modelNum}.")
        self.ssnmf_tol = ssnmf_tol
        self.hyp_search = hyp_search
        self.modelNum = modelNum

        if self.hyp_search == 0:
            self.opt_ka = ka
            self.opt_lamb = lamb
            self.opt_itas = itas
        else:
            eval_module = Evaluation(train_features = self.X_train,
                                     train_labels = self.y_train,
                                     test_features = self.X_val, test_labels = self.y_val,
                                     k = ka, modelNum = self.modelNum, tol = self.ssnmf_tol)

            self.opt_lamb, self.opt_ka, self.opt_itas = eval_module.iterativeLocalSearch(init_lamb=lamb, init_k=ka, init_itas=itas)

        eval_module = Evaluation(train_features = self.X_train_full,
                                 train_labels = self.y_train_full,
                                 test_features = self.X_test, test_labels = self.y_test, tol = self.ssnmf_tol,
                                 modelNum = self.modelNum, k = self.opt_ka, lam=self.opt_lamb, numiters = self.opt_itas)

        train_evals, test_evals = eval_module.eval()
        ssnmf_iter = len(train_evals[0])

        #print(f"The classification accuracy on the train data is {train_evals[-1][-1]*100:.4f}%")
        print(f"The classification accuracy on the test data is {test_evals[-1]*100:.4f}%")

        Y_predicted = eval_module.model.B@eval_module.S_test
        ssnmf_predicted = np.argmax(Y_predicted, axis=0)+1

        S = eval_module.model.S
        S_test = eval_module.S_test

        if print_results == 1:
            print(metrics.classification_report(self.test_labels, ssnmf_predicted, target_names=self.cls_names))
            # Plot B matrix
            factors_heatmaps(eval_module.model.B, cls_names=self.cls_names, save=True)
            # Plot normalized B matrix
            B_norm = eval_module.model.B/eval_module.model.B.sum(axis=0)[None,:]
            factors_heatmaps(B_norm, cls_names=self.cls_names)
            # Extract top keywords representaion of topics
            print_keywords(eval_module.model.A.T, features=self.feature_names_train, top_num=10)

        return test_evals, eval_module.model.A, eval_module.model.B, ssnmf_predicted, ssnmf_iter, S, S_test


    def run_analysis(self, ssnmf_tol, nmf_tol, lamb, ka, itas, iterations, print_results=0, hyp_search=0):
        """
        Compute and save all results for each iteration of each model.

        Args:
            ssnmf_tol (list): list of tolerance values for termanating SSNMF Models [3,4,5,6] respecitvely
            nmf_tol (list): tolerance for termanating NMF model
            lamb (list): list of regularization parameter of SSNMF Models [3,4,5,6] respecitvely
            ka (int): input rank for SSNMF
            itas (int): maximum number of multiplicative update iterations
            iterations (int): (odd) number of iterations to run for analysis
            print_results (boolean): 1: print classification report, heatmaps, and keywords, 0:otherwise
            hyp_search (boolean): 0: run hyperparameter search algorithm, 1:otherwise
        Returns:
            acc_dict (dictionary): for each model, test accuracy for each iteration (list)
            A_dict (dictionary): for each model, word dictionary matrices for each iteration (list) (if applicable)
            B_dict (dictionary): for each model, classification dictionary matrices for each iteration (list) (if applicable)
            S_dict (dictionary): for each model, train (+test) document representaion matrices for each iteration (list) (if applicable)
            S_test_dict  (dictionary): for each model, test document representaion matrices for each iteration (list) (if applicable)
            Yhat_dict (dictionary): for each model, predicted labels for each iteration (list)
            median_dict (dictionary): for each model, indices of the median model for each model based on test accuracy
            iter_dict (dictionary): for each model, number of multiplicative updates for each iteration (list) (if applicable)

        """
        print("\nRunning analysis.")

        self.hyp_search = hyp_search
        acc_dict = {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": [], "NB": [], "SVM": []}
        A_dict= {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": []}
        B_dict= {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": []}
        S_dict= {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": []}
        S_test_dict= {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": []}
        Yhat_dict = {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": [], "NB": [], "SVM": []}
        iter_dict = {"Model3": [], "Model4": [], "Model5": [], "Model6": [], "NMF": []}

        # Construct an evaluation module
        evalualtion_module = Methods(X_train = self.X_train, X_val = self.X_val, X_test = self.X_test,\
                                train_labels = self.train_labels, val_labels = self.val_labels,\
                                test_labels = self.test_labels, X_train_full = self.X_train_full,\
                                train_labels_full = self.train_labels_full, cls_names = self.cls_names,\
                                feature_names_train=self.feature_names_train)

        # Run NB
        nb_acc, nb_predicted = list(evalualtion_module.MultinomialNB())
        acc_dict["NB"].append(nb_acc)
        Yhat_dict["NB"].append(nb_predicted)

        for j in range(iterations):
            print(f"Iteration {j}.")
            for i in range(3,7):
                # Run SSNMF
                test_evals, A, B, ssnmf_predicted, ssnmf_iter, S, S_test = evalualtion_module.SSNMF(modelNum = i, ssnmf_tol = ssnmf_tol[i-3],lamb = lamb[i-3],\
                                                                                        ka = ka, itas= itas, print_results = print_results, hyp_search = self.hyp_search)
                acc_dict["Model" + str(i)].append(test_evals[-1])
                A_dict["Model" + str(i)].append(A)
                B_dict["Model" + str(i)].append(B)
                S_dict["Model" + str(i)].append(S)
                S_test_dict["Model" + str(i)].append(S_test)
                Yhat_dict["Model" + str(i)].append(ssnmf_predicted)
                iter_dict["Model" + str(i)].append(ssnmf_iter)

            # Run NMF + SVM
            nmf_svm_acc, W, nn_svm, nmf_svm_predicted, nmf_iter, H, H_test = evalualtion_module.NMF(rank=ka, nmf_tol= nmf_tol, print_results=print_results)
            acc_dict["NMF"].append(nmf_svm_acc)
            A_dict["NMF"].append(W)
            B_dict["NMF"].append(nn_svm)
            S_dict["NMF"].append(H)
            S_test_dict["NMF"].append(H_test)
            Yhat_dict["NMF"].append(nmf_svm_predicted)
            iter_dict["NMF"].append(nmf_iter)

            # Run SVM
            svm_acc, svm_predicted = list(evalualtion_module.SVM())
            acc_dict["SVM"].append(svm_acc)
            Yhat_dict["SVM"].append(svm_predicted)

            # Save all dictionaries
            pickle.dump(acc_dict, open("acc_dict.pickle", "wb"))
            pickle.dump(A_dict, open("A_dict.pickle", "wb"))
            pickle.dump(B_dict, open("B_dict.pickle", "wb"))
            pickle.dump(S_dict, open("S_dict.pickle", "wb"))
            pickle.dump(S_test_dict, open("S_test_dict.pickle", "wb"))
            pickle.dump(Yhat_dict, open("Yhat_dict.pickle", "wb"))
            pickle.dump(iter_dict, open("iter_dict.pickle", "wb"))

        # Report average performance for models
        print("\n\nPrinting mean + std accuracy results...")
        print("---------------------------------------\n")
        for i in range(3,7):
            acc = acc_dict["Model" + str(i)]
            print(f"Model {i} average accuracy: {mean(acc):.4f} ± {stdev(acc):.4f}.")
        acc = acc_dict["NMF"]
        print(f"NMF average accuracy: {mean(acc):.4f} ± {stdev(acc):.4f}.")
        acc = acc_dict["NB"][0]
        print(f"NB accuracy: {acc:.4f}.")
        acc = acc_dict["SVM"]
        print(f"SVM average accuracy: {mean(acc):.4f} ± {stdev(acc):.4f}.")

        # Report average number of iterations (mult. updates) for models
        print("\n\nPrinting mean number of iterations (multiplicative updates)...")
        print("----------------------------------------------------------------\n")
        for i in range(3,7):
            iter_list = iter_dict["Model" + str(i)]
            print(f"Model {i} average number of iterations: {mean(iter_list):.2f}.")
        iter_list = iter_dict["NMF"]
        print(f"NMF average number of iterations: {mean(iter_list):.2f}.")

        # Find median performance for models
        print("\n\nPrinting median accuracy results...")
        print("---------------------------------------\n")
        median_dict = {}
        for i in range(3,7):
            acc = acc_dict["Model" + str(i)]
            median_dict["Model" + str(i)] = np.argsort(acc)[len(acc)//2]
            print(f"Model {i} median accuracy: {median(acc):.4f}.")

        acc = acc_dict["NMF"]
        median_dict["NMF"] = np.argsort(acc)[len(acc)//2]
        print(f"NMF median accuracy: {median(acc):.4f}.")

        acc = acc_dict["NB"][0]
        print(f"NB accuracy: {acc:.4f}.")

        acc = acc_dict["SVM"]
        median_dict["SVM"] = np.argsort(acc)[len(acc)//2]
        print(f"SVM median accuracy: {median(acc):.4f}.")

        pickle.dump(median_dict, open("median_dict.pickle", "wb"))
        pickle.dump([ssnmf_tol, nmf_tol, lamb, ka, itas, iterations, hyp_search], open("param_list.pickle", "wb"))

        return acc_dict, A_dict, B_dict, S_dict, S_test_dict, Yhat_dict, median_dict, iter_dict

    def median_results(self, acc_dict, A_dict, B_dict, Yhat_dict, median_dict, iter_dict):
        """
        Print classification reports, heatmaps (if applicable), and keywords of the median model results.
        Args:
            acc_dict (dictionary): for each model, test accuracy for each iteration (list)
            A_dict (dictionary): for each model, word dictionary matrices for each iteration (list) (if applicable)
            B_dict (dictionary): for each model, classification dictionary matrices for each iteration (list) (if applicable)
            Yhat_dict (dictionary): for each model, predicted labels for each iteration (list)
            median_dict (dictionary): for each model, indices of the median model for each model based on test accuracy
            iter_dict (dictionary): for each model, number of multiplicative updates for each iteration (list) (if applicable)
        """

        print("\n\nPrinting classification report, keywords, and heatmaps for median model results.")
        print("-----------------------------------------------------------------------------------\n")
        for i in range(3,7):
            print(f"\nSSNMF Model {i} results.\n")
            A = A_dict["Model" + str(i)][median_dict["Model" + str(i)]]
            B = B_dict["Model" + str(i)][median_dict["Model" + str(i)]]
            ssnmf_predicted = Yhat_dict["Model" + str(i)][median_dict["Model" + str(i)]]
            iter = iter_dict["Model" + str(i)][median_dict["Model" + str(i)]]

            print(metrics.classification_report(self.test_labels, ssnmf_predicted, target_names=self.cls_names))
            factors_heatmaps(B, cls_names=self.cls_names, save=True, filepath = 'SSNMF_Model{}.png'.format(i))
            B_norm = B/B.sum(axis=0)[None,:]
            factors_heatmaps(B_norm, cls_names=self.cls_names, save=True, filepath = 'SSNMF_Model{}_Normalized.png'.format(i))
            print_keywords(A.T, features=self.feature_names_train, top_num=10)
            print(f"\nSSNMF Model {i} number of iterations {iter}.\n")

        print(f"\nNMF results.\n")
        W = A_dict["NMF"][median_dict["NMF"]]
        nn_svm = B_dict["NMF"][median_dict["NMF"]]
        nmf_svm_predicted = Yhat_dict["NMF"][median_dict["NMF"]]
        iter = iter_dict["NMF"][median_dict["NMF"]]
        print(metrics.classification_report(self.test_labels, nmf_svm_predicted, target_names=self.cls_names))
        print_keywords(W.T, features=self.feature_names_train, top_num=10)
        factors_heatmaps(nn_svm, cls_names=self.cls_names, save = True, filepath = 'NMF.png')
        nn_svm_norm = nn_svm/nn_svm.sum(axis=0)[None,:]
        factors_heatmaps(nn_svm_norm, cls_names=self.cls_names, save = True, filepath = 'NMF_Normalized.png')
        print(f"\nNMF model number of iterations {iter}.\n")

        print(f"\nNB results.\n")
        nb_predicted = Yhat_dict["NB"][0]
        print(metrics.classification_report(self.test_labels, nb_predicted, target_names=self.cls_names))

        print(f"\nSVM results.\n")
        svm_predicted = Yhat_dict["SVM"][median_dict["SVM"]]
        print(metrics.classification_report(self.test_labels, svm_predicted, target_names=self.cls_names))