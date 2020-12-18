import numpy as np
import torch

from naslib.optimizers.core.metaclasses import MetaOptimizer
from naslib.search_spaces.core.query_metrics import Metric

from naslib.optimizers.discrete.utils.utils import sample_random_architecture
    

class RandomSearch(MetaOptimizer):
    """
    Random search in DARTS is done by randomly sampling `k` architectures
    and training them for `n` epochs, then selecting the best architecture.
    DARTS paper: `k=24` and `n=100` for cifar-10.
    """

    # training the models is not implemented
    using_step_function = False

    def __init__(self, config, weight_optimizer=torch.optim.SGD, loss_criteria=torch.nn.CrossEntropyLoss(), grad_clip=None):
        """
        Initialize a random search optimizer.

        Args:
            config
            weight_optimizer (torch.optim.Optimizer): The optimizer to 
                train the (convolutional) weights.
            loss_criteria (TODO): The loss
            grad_clip (float): Where to clip the gradients (default None).
        """
        super(RandomSearch, self).__init__()
        self.weight_optimizer = weight_optimizer
        self.loss = loss_criteria
        self.grad_clip = grad_clip

        self.performance_metric = Metric.VAL_ACCURACY
        self.dataset = config.dataset
        self.fidelity = config.search.fidelity

        
        self.sampled_archs = []
        self.history = torch.nn.ModuleList()


    def adapt_search_space(self, search_space, scope=None):
        assert search_space.QUERYABLE, "Random search is currently only implemented for benchmarks."
        self.search_space = search_space.clone()
        self.scope = scope if scope else search_space.OPTIMIZER_SCOPE


    def new_epoch(self, e):
        """
        Sample a new architecture to train.
        """

        model = torch.nn.Module()   # hacky way to get arch and accuracy checkpointable
        model.arch = sample_random_architecture(self.search_space, self.scope)
        model.accuracy = model.arch.query(self.performance_metric, self.dataset, epoch=self.fidelity)

        self.sampled_archs.append(model)
        self._update_history(model)

        # required if we want to train the models and not only query.
        # architecture_i.parse()
        # architecture_i.train()
        # architecture_i = architecture_i.to(torch.device("cuda:0" if torch.cuda.is_available() else "cpu"))
        # self.sampled_archs.append(architecture_i)
        # self.weight_optimizers.append(self.weight_optimizer(architecture_i.parameters(), 0.01))


    def _update_history(self, child):
        if len(self.history) < 100:
            self.history.append(child)
        else:
            for i, p in enumerate(self.history):
                if child.accuracy > p.accuracy:
                    self.history[i] = child
                    break


    def get_final_architecture(self):
        """
        Returns the sampled architecture with the lowest validation error.
        """
        return max(self.sampled_archs, key=lambda x: x.accuracy).arch


    def train_statistics(self):
        best_arch = self.get_final_architecture()
        return (
            best_arch.query(Metric.TRAIN_ACCURACY, self.dataset), 
            best_arch.query(Metric.TRAIN_LOSS, self.dataset), 
            best_arch.query(Metric.VAL_ACCURACY, self.dataset), 
            best_arch.query(Metric.VAL_LOSS, self.dataset), 
        )


    def test_statistics(self):
        best_arch = self.get_final_architecture()
        return best_arch.query(Metric.RAW, self.dataset)


    def get_op_optimizer(self):
        return self.weight_optimizer


    def get_checkpointables(self):
        return {'model': self.history}
