from django.test import TestCase
from .. import models as models_module
from computedfields.models import active_resolver
MODELS = models_module.MODELS


class GenericModelTestBase(TestCase):
    """
    Test base class to provide a customizable function and depends settings for the
    autogenerated models in various test cases.
    """
    models = models_module

    def setDeps(self, mapping):
        """
        Sets the depends values and func to a model and rebuilds the graph
        and handler mappings. The models come only with one computed field `comp`.
        All settings are applied to this field.
        Mapping should be {'modelname': {'depends' ['depend', 'strings'], 'func': some_func}}.
        Might raise a `CycleNodeException`.
        """
        models = active_resolver.computed_models
        for modelname, data in mapping.items():
            if data.get('depends'):
                models[MODELS[modelname]]['comp']._computed['depends'] = data.get('depends')
            if data.get('func'):
                models[MODELS[modelname]]['comp']._computed['func'] = data.get('func')
        active_resolver.load_maps(_force_recreation=True)
        self.graph = active_resolver._graph

    def resetDeps(self):
        """
        Resets all depends and function values to initial dummies.
        Only applied to auto generated models.
        """
        models = active_resolver.computed_models
        for model in models:
            if not hasattr(model, 'needs_reset'):
                continue
            models[model]['comp']._computed['depends'] = {}
            for fieldname, f in models[model].items():
                f._computed['func'] = lambda x: ''
        self.graph = None
