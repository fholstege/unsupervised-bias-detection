import numpy as np
import heapq
from abc import ABC, abstractmethod
from sklearn.base import BaseEstimator, ClusterMixin


class BiasAwareHierarchicalClustering(ABC, BaseEstimator, ClusterMixin):
    """
    Base class for Bias-Aware Hierarchical Clustering.

    This abstract class specifies an interface for all bias-aware hierarchical clustering classes.

    References
    ----------
    .. [1] J. Misztal-Radecka, B. Indurkhya, "Bias-Aware Hierarchical Clustering for detecting the discriminated
           groups of users in recommendation systems", Information Processing & Management, vol. 58, no. 3, May. 2021.
    """

    def __init__(self, n_iter, min_cluster_size):
        self.n_iter = n_iter
        self.min_cluster_size = min_cluster_size

    def calc_centroids(self, X, labels):
        """ Calculate the centroids of the clusters based on the labels

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            List of n_features-dimensional data points. Each row
            corresponds to a single data point.
        labels : array-like of shape (n_samples)
            Cluster labels for each point.
        
        """

        # create an array of (d, k) with d being the number of features and k the number of unique labels
        centroids = np.zeros((X.shape[1], len(np.unique(labels))))

        # iterate over the labels
        for i, label in enumerate(np.unique(labels)):

            # get the data points that belong to the cluster with the current label
            X_label = X[labels == label]

            # calculate the mean of the data points
            centroids[:, i] = np.mean(X_label, axis=0)

        return centroids

    def fit(self, X, y):
        """Compute bias-aware hierarchical clustering.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            List of n_features-dimensional data points. Each row
            corresponds to a single data point.
        y : array-like of shape (n_samples)
            Metric values.

        Returns
        -------
        self : object
            Fitted estimator.
        """
        X, y = self._validate_data(
            X, y, reset=False, accept_large_sparse=False, dtype=self._dtype, order="C"
        )
        n_samples, _ = X.shape
        # We start with all samples in a single cluster
        self.n_clusters_ = 1
        # We assign all samples a label of zero
        labels = np.zeros(n_samples, dtype=np.uint32)
        clusters = []
        scores = []
        label = 0
        # The entire dataset has a discrimination score of zero
        score = 0
        heap = [(None, label, score)]
        for _ in range(self.n_iter):
            if not heap:
                # If the heap is empty we stop iterating
                break
            # Take the cluster with the highest standard deviation of metric y
            _, label, score = heapq.heappop(heap)
            cluster_indices = np.nonzero(labels == label)[0]
            cluster = X[cluster_indices]
            cluster_labels = self._split(cluster)
            indices0 = cluster_indices[np.nonzero(cluster_labels == 0)[0]]
            indices1 = cluster_indices[np.nonzero(cluster_labels == 1)[0]]
            if (
                len(indices0) >= self.min_cluster_size
                and len(indices1) >= self.min_cluster_size
            ):
                # We calculate the discrimination scores using formula (1) in [1]
                mask0 = np.ones(n_samples, dtype=bool)
                mask0[indices0] = False
                score0 = np.mean(y[mask0]) - np.mean(y[indices0])
                mask1 = np.ones(n_samples, dtype=bool)
                mask1[indices1] = False
                score1 = np.mean(y[mask1]) - np.mean(y[indices1])
                if max(score0, score1) >= score:
                    # heapq implements min-heap
                    # so we have to negate std before pushing
                    std0 = np.std(y[indices0])
                    heapq.heappush(heap, (-std0, label, score0))
                    std1 = np.std(y[indices1])
                    heapq.heappush(heap, (-std1, self.n_clusters_, score1))
                    labels[indices1] = self.n_clusters_
                    self.n_clusters_ += 1
                else:
                    clusters.append(label)
                    scores.append(score)
            else:
                clusters.append(label)
                scores.append(score)
        clusters = np.array(clusters + [label for _, label, _ in heap])
        scores = np.array(scores + [score for _, _, score in heap])
        # We sort clusters by decreasing scores
        indices = np.argsort(-scores)
        clusters = clusters[indices]
        self.scores_ = scores[indices]
        mapping = np.zeros(self.n_clusters_, dtype=np.uint32)
        mapping[clusters] = np.arange(self.n_clusters_, dtype=np.uint32)
        self.labels_ = mapping[labels]


        # Fit the centroids
        self.centroids_ = self.calc_centroids(X, self.labels_)

        return self
    
    def predict(self, X):
        """Predict the cluster labels for the samples in X.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            List of n_features-dimensional data points. Each row
            corresponds to a single data point.

        Returns
        -------
        labels : array-like of shape (n_samples,)
            Cluster labels for each point.
        """

        # Validate the data
        X = self._validate_data(
            X, reset=False, accept_large_sparse=False, dtype=self._dtype, order="C"
        )
       # Get dimensions
        n_samples = X.shape[0]
        n_clusters = self.centroids_.shape[1]
        
        # Initialize distance matrix
        distances = np.zeros((n_samples, n_clusters))
        
        # Compute squared Euclidean distance between each sample and each centroid
        for k in range(n_clusters):

            # Deduct the centroid from the data
            diff = X - self.centroids_[:, k].T

            # Calculate the sum of squared differences
            distances[:, k] = np.sum(diff * diff, axis=1)
        
        # Get the index (label) of the closest centroid for each sample
        labels = np.argmin(distances, axis=1)
        
        
        return labels

    @abstractmethod
    def _split(self, X):
        """Split the data into two clusters.

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_features)

        Returns
        -------
        labels : ndarray of shape (n_samples,)
            Cluster labels for each point. Every label is either 0 or 1 indicating
            that the point belongs to the first or the second cluster, respectively.
        """
        pass
