
import os
import sys
from glob import glob
from importlib.util import spec_from_file_location, module_from_spec

from zegami_sdk.trained_model import TrainedModel


class MrcnnTrainedModel(TrainedModel):
    
    TYPE = 'mrcnn'
    
    def __init__(self, save_path, **kwargs):
        """
        - save_path:
            Path to a directory containing all relevant saved mrcnn inference
            loading data. Expected:
                - A .h5 file (automatically uses last of a **/*.h5 glob query)
                - A python file called 'inference_config.py' with a class
                  in it called 'InferenceConfig()' to instantiate from.
            
        Optional kwargs:
            
        - use_mrcnn_exclusion:
            This is required for base weights (coco), not manually trained
            weights. It is like this won't ever be needed if this trained
            model always uses manually training results.
        """
        
        # Check basic requirements and save_path existence
        super().__init__(save_path, **kwargs)
        
        # Load data
        self.config = self.load_config()
        self.model = self.load_model()
    
    def load_config(self):
        """
        Loads the inference configuration, looking for a file in save_path
        called 'inference_config.py'.
        """
        
        print('\n[Loading Config]')
        
        fp = os.path.join(self.save_path, 'inference_config.py')
        if not os.path.exists(fp):
            raise FileNotFoundError(
                'Expected to find configuration file at "{}"'.format(fp))
            
        # Load the file as a module
        spec = spec_from_file_location('inference_config', fp)
        inference_config = module_from_spec(spec)
        sys.modules['inference_config'] = inference_config
        spec.loader.exec_module(inference_config)
        
        # Instantiate the config
        self.config = inference_config.InferenceConfig()
        
        # Readout
        print('Inference Config:')
        for k in [_ for _ in dir(self.config) if not _.startswith('__') and not callable(getattr(self.config, _))]:
            print('{:<20} {}'.format(k, getattr(self.config, k)))
        
    def load_model(self):
        """
        Loads the model using the already-instantiated inference config and
        last-found .h5 weights file in the save directory.
        """
        
        from zegami_ai.mrcnn.architecture.model import MaskRCNN
        
        print('\n[Loading Model]')
        
        # Ensure weights
        regex = '{}**/*.h5'.format(self.save_path)
        candidates = [str(g) for g in glob(regex, recursive=True)]
        if len(candidates) == 0:
            raise FileNotFoundError(
                'No weights files found in "{}"'.format(self.save_path))
        elif len(candidates) > 1:
            wfp = candidates[-1]
            print('Multiple weights found: "{}"'.format(candidates))
            print('Using weights: "{}"'.format(candidates[-1]))
        else:
            wfp = candidates[0]
            print('Using weights: "{}"'.format(os.path.basename(wfp)))
            
        # Potentially use mrcnn exclusion (used with fresh coco weights)
        mrcnn_exclusion = []
        use_mrcnn_exclusion = self.kwargs.get('use_mrcnn_exclusion', False)
        if use_mrcnn_exclusion:
            mrcnn_exclusion = [
                'mrcnn_class_logits', 'mrcnn_bbox_fc', 'mrcnn_bbox', 
                'mrcnn_mask', 'rpn_model']
            print('Using mrcnn exclusion (untouched external weights)')
        
        # Load the model
        print('Instantiating model')
        model = MaskRCNN('inference', self.config, '.')
        
        print('Loading weights')
        model.load_weights(wfp, by_name=True, exclusion=mrcnn_exclusion)
        
        print('Compiling model')
        lr = self.config.LEARNING_RATE
        lm = self.config.LEARNING_MOMENTUM
        model.compile(lr, lm)
        
        self.model = model