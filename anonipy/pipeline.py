from .anonymize.extractors import ExtractorInterface, MultiExtractor
from .anonymize.strategies import StrategyInterface
from .utils.file_system import *
import json
from typing import Union, List
import os

# =====================================
# Pipeline class
# =====================================

class Pipeline():
    """ A class for anonymizing files using a pipeline of extractors and strategies.

        Examples:
            >>> from anonipy.pipeline import Pipeline    
            >>> extractor = NERExtractor(labels, lang=LANGUAGES.ENGLISH)
            >>> strategy = RedactionStrategy()        
            >>> pipeline = Pipeline(extractor, strategy)        
            >>> pipeline.anonymize(r"/path/to/input_dir", r"/path/to/output_dir", False)    
    
        Attributes:
            extractor (ExtractorInterface): The extractor to use for entity extraction.
            strategy (StrategyInterface): The strategy to use for anonymization.

        Methods:
            anonymize(input_dir, output_dir, flatten=False): Anonymize files in the input directory and save the anonymized files to the output directory. 

        """
    
    def __init__(self, extractor: Union[ExtractorInterface, List[ExtractorInterface]], strategy: StrategyInterface):
        """ Initialize the pipeline.

            Examples:
                >>> from anonipy.pipeline import Pipeline    
                >>> extractor = NERExtractor(labels, lang=LANGUAGES.ENGLISH)
                >>> strategy = RedactionStrategy()        
                >>> pipeline = Pipeline(extractor, strategy)

            Args:
                extractor (Union[ExtractorInterface, List[ExtractorInterface]]): The extractor to use for entity extraction.
                strategy (StrategyInterface): The strategy to use for anonymization.    
            
        """

        try:
            if isinstance(extractor, ExtractorInterface):
                self.extractor = extractor
            elif isinstance(extractor, list):
                self.extractor = MultiExtractor(extractor)
            else:
                raise ValueError("Extractor must be an ExtractorInterface or a list of ExtractorInterface.")
        except Exception as e:
            print(f"Failed to initialize extractor: {e}")
            raise
        
        if not isinstance(strategy, StrategyInterface):
            raise ValueError("Strategy must be a StrategyInterface.")
        
        self.strategy = strategy
        self.anonymized_files_count = 0

    def anonymize(self, input_dir: str, output_dir: str, flatten: bool = False) -> str:
        """ Anonymize files in the input directory and save the anonymized files to the output directory.

            Args:
                input_dir (str): The path to the input directory containing files to be anonymized.
                output_dir (str): The path to the output directory where anonymized files will be saved.
                flatten (bool, optional): Whether to flatten the output directory structure. Defaults to False.

            Raises:
                ValueError: If the input directory does not exist or if the input and output directories are the same.

            Returns:    
                str: A JSON string containing a mapping of input file paths to their corresponding anonymized file names.
        """

        if not os.path.exists(input_dir):
            raise ValueError(f"Input directory '{input_dir}' does not exist.")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        if os.path.abspath(input_dir) == os.path.abspath(output_dir):
            raise ValueError("Input and output directories cannot be the same.")
    
        file_name_mapping = {}
        for root, _, files in os.walk(input_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                try:
                    anonymized_text = self._anonymize_file(file_path)
                    if not anonymized_text.strip():
                        print(f"Skipping file {file_path}: Anonymized text is empty.")
                        continue
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
                    continue

                base_name, ext = os.path.splitext(file_name)
                self.anonymized_files_count += 1
                base_name = f"file{self.anonymized_files_count}"
                output_file_name = f"{base_name}_anony{ext}"
                relative_path = os.path.relpath(file_path, input_dir)
                
                if flatten:
                    output_file_path = os.path.join(output_dir, output_file_name)
                else:
                    output_file_path = os.path.join(output_dir, os.path.dirname(relative_path), output_file_name)
                    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

                write_file(anonymized_text, output_file_path)

                file_path_before = os.path.join(input_dir.split(os.sep)[-1], relative_path)
                file_path_after = os.path.relpath(output_file_path, output_dir)
                file_name_mapping[file_path_before] = os.path.join(output_dir.split(os.sep)[-1], file_path_after)

        return json.dumps(file_name_mapping, indent=4, sort_keys=True)
    
    def _anonymize_file(self, file_path: str) -> str: 
        """ Anonymize a single file.

            Args:
                file_path (str): The path to the file to be anonymized.

            Returns:
                str: The anonymized text.
        """

        original_text = open_file(file_path)
        if original_text is None:
            print(f"Skipping file {file_path}: Failed to read or file is empty.")
            return ""

        doc, entities = self.extractor(original_text)

        if entities is None:
            print(f"Skipping file {file_path}: Entity extraction returned None.")
            return ""
    
        anonymized_text, replacements = self.strategy.anonymize(original_text, entities)

        return anonymized_text