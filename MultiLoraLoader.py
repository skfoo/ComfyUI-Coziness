# https://github.com/skfoo/ComfyUI-Coziness

import folder_paths
import comfy.utils
import comfy.sd
import os
import re

KEY_BLOCKS_ALL = "all_blocks"
KEY_BLOCKS_ALL_ABBR = "allb"
KEY_BLOCKS_SINGLE = "single_blocks"
KEY_BLOCKS_SINGLE_ABBR = "msb"
KEY_BLOCKS_DOUBLE = "double_blocks"
KEY_BLOCKS_DOUBLE_ABBR = "mdb"

class MultiLoraLoader:
    def __init__(self):
        self.selected_loras = SelectedLoras()
    
    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "model": ("MODEL",),
                              "text": ("STRING", {
                                "multiline": True,
                                "default": ""}),
                            },
                "optional": {"clip": ("CLIP", ),}}

    RETURN_TYPES = ("MODEL", "CLIP")
    FUNCTION = "load_loras"
    CATEGORY = "loaders"

    def load_loras(self, model, text, clip = None):
        result = (model, clip)
        
        lora_items = self.selected_loras.updated_lora_items_with_text(text)

        if len(lora_items) > 0:
            for item in lora_items:
                result = item.apply_lora(result[0], result[1])
            
        return result

class MultiLoraParser:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": ""
                }),
            }
        }

    RETURN_TYPES = ("LORA_INFO",)
    RETURN_NAMES = ("Lora Info List",)
    FUNCTION = "parse_loras"
    CATEGORY = "utils"

    def __init__(self):
        self.selected_loras = SelectedLoras()

    @staticmethod
    def get_block_list(blocks):
        return list()

    def parse_loras(self, text):
        lora_items = self.selected_loras.updated_lora_items_with_text(text)

        parsed_info = []
        for item in lora_items:
            lora_path = item.get_lora_path()
            parsed_info.append({
                "path": lora_path,
                "strength": item.strength_model,
                "name": item.lora_name,
                "blocks": list() if KEY_BLOCKS_ALL in item.blocks else MultiLoraParser.get_block_list(item.blocks),
                "low_mem_load": False  # Can be expanded later if needed
            })

        return (parsed_info,)

class LoraInfoToHunyuanVidLora:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "lora_info": ("LORA_INFO",),
            }
        }

    RETURN_TYPES = ("HYVIDLORA",)
    FUNCTION = "passthrough"
    CATEGORY = "utils"

    def passthrough(self, lora_info):
        return (lora_info,)

class LoraInfoToWanVidLora:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "lora_info": ("LORA_INFO",),
            }
        }

    RETURN_TYPES = ("WANVIDLORA",)
    FUNCTION = "passthrough"
    CATEGORY = "utils"

    def passthrough(self, lora_info):
        return (lora_info,)
 
# maintains a list of lora objects made from a prompt, preserving loaded loras across changes
class SelectedLoras:
    def __init__(self):
        self.lora_items = []

    # returns a list of loaded loras using text from LoraTextExtractor
    def updated_lora_items_with_text(self, text):
        available_loras = self.available_loras()
        self.update_current_lora_items_with_new_items(self.items_from_lora_text_with_available_loras(text, available_loras))
        
        for item in self.lora_items:
            if item.lora_name not in available_loras:
                raise ValueError(f"Unable to find lora with name '{item.lora_name}'")
            
        return self.lora_items

    def available_loras(self):
        return folder_paths.get_filename_list("loras")
    
    def items_from_lora_text_with_available_loras(self, lora_text, available_loras):
        return LoraItemsParser.parse_lora_items_from_text(lora_text, self.dictionary_with_short_names_for_loras(available_loras))
    
    def dictionary_with_short_names_for_loras(self, available_loras):
        result = {}
        
        for path in available_loras:
            result[os.path.splitext(os.path.basename(path))[0]] = path
        
        return result

    def update_current_lora_items_with_new_items(self, lora_items):
        if self.lora_items != lora_items:
            existing_by_name = dict([(existing_item.lora_name, existing_item) for existing_item in self.lora_items])
            
            for new_item in lora_items:
                new_item.move_resources_from(existing_by_name)
            
            self.lora_items = lora_items

class LoraItemsParser:

    @classmethod
    def parse_lora_items_from_text(cls, lora_text, loras_by_short_names = {}, default_weight=1, weight_separator=":"):
        return cls(lora_text, loras_by_short_names, default_weight, weight_separator).execute()

    def __init__(self, lora_text, loras_by_short_names, default_weight, weight_separator):
        self.lora_text = lora_text
        self.loras_by_short_names = loras_by_short_names
        self.default_weight = default_weight
        self.weight_separator = weight_separator
        self.prefix_trim_re = re.compile("\A<(lora|lyco):")
        self.comment_trim_re = re.compile("\s*#.*\Z")
    
    def execute(self):

        out_loras = []

        for line in self.lora_text.splitlines():
            description = self.description_from_line(line)
            name, model_weight, clip_weight, block_type = self.parse_lora_description(description)
            if name is not None:
                out_loras.append(LoraItem(name, model_weight, clip_weight, block_type))
                    
        return out_loras
    
    def parse_lora_description(self, description):
        if description is None:
            return (None, None, None, None)
        
        lora_name = None
        strength_model = self.default_weight
        strength_clip = None
        blocks = []
        
        parts = description.split(self.weight_separator)

        def is_block_param(param):
            return param.split("[")[0] in [KEY_BLOCKS_ALL, KEY_BLOCKS_ALL_ABBR, KEY_BLOCKS_SINGLE, KEY_BLOCKS_SINGLE_ABBR, KEY_BLOCKS_DOUBLE, KEY_BLOCKS_DOUBLE_ABBR]
    
        try:
            if len(parts) == 1:  # Only lora name
                lora_name = parts[0]
            elif len(parts) == 2:  # lora name and model weight or blocks
                lora_name, last_param = parts
                if "blocks" in last_param:
                    blocks = [last_param]
                else:
                    strength_model = float(last_param)
            elif len(parts) == 3:  # lora name, model weight, and either clip weight or blocks
                lora_name, strength_model, last_param = parts
                strength_model = float(strength_model)
                if is_block_param(last_param):
                    blocks = [last_param]
                else:
                    strength_clip = float(last_param)
            elif len(parts) == 4:  # name, model weight, clip weight, blocks (single or double) OR name, model weight, blocks (single and double)
                lora_name, strength_model, second_to_last_param, last_param = parts
                strength_model = float(strength_model)
                if is_block_param(second_to_last_param):
                    blocks = [second_to_last_param]
                else:
                    strength_clip = float(second_to_last_param)
                blocks.append(last_param)
            elif len(parts) == 5:  # lora name, model weight, clip weight, single blocks, double blocks (block position is interchangeable)
                lora_name, strength_model, strength_clip, blocksA, blocksB = parts
                strength_model = float(strength_model)
                strength_clip = float(strength_clip)
                blocks = [blocksA, blocksB]
        except ValueError as e:
            raise ValueError(f"Invalid description format: {description}") from e
        
        if strength_clip is None:
            strength_clip = strength_model

        def parse_ranges(input_str, max_range=100):
            result = set()
            for part in input_str.split(','):
                part = part.strip()  # Remove extra spaces
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        # Add range as strings
                        result.update(map(str, range(min(start, end), max(start, end) + 1)))
                    except ValueError as e:
                        raise ValueError(f"Invalid numeric range: {e}")
                elif "even" in part:
                    # Add even numbers as strings
                    result.update(map(str, range(0, max_range + 1, 2)))
                elif "odd" in part:
                    # Add odd numbers as strings
                    result.update(map(str, range(1, max_range + 1, 2)))
                elif part.isdigit():  # Single numeric value
                    result.add(part)
                elif part:  # Handle non-numeric strings
                    result.add(part)
            return result

        valid_blocks = [KEY_BLOCKS_SINGLE, KEY_BLOCKS_SINGLE_ABBR, KEY_BLOCKS_DOUBLE, KEY_BLOCKS_DOUBLE_ABBR]
        if not blocks:
            blocks = {KEY_BLOCKS_ALL: []}
        else:
            # Split compound block strings like `double_blocks[1-10]`
            normalized_blocks = {}
            for block in blocks:
                # Remove whitespace and expand abbreviations
                block = block.strip().replace(KEY_BLOCKS_SINGLE_ABBR, KEY_BLOCKS_SINGLE).replace(KEY_BLOCKS_DOUBLE_ABBR, KEY_BLOCKS_DOUBLE)
                if "[" in block and "]" in block:
                    block_type, indices = block.split("[", 1)
                    block_type = block_type.strip()
                    indices = indices.rstrip("]").strip()
                    if block_type in valid_blocks:
                        normalized_blocks[block_type] = parse_ranges(indices)
                elif block in valid_blocks:
                    normalized_blocks[block] = set()
                else:
                    raise ValueError(f"Invalid block type or format: {block}")
            blocks = normalized_blocks

        return (self.loras_by_short_names.get(lora_name, lora_name), strength_model, strength_clip, blocks)


    def description_from_line(self, line):
        result = self.comment_trim_re.sub("", line.strip())
        result = self.prefix_trim_re.sub("", result.removesuffix(">"))
        return result if len(result) > 0 else None
        

class LoraItem:
    def __init__(self, lora_name, strength_model, strength_clip, blocks_type):
        self.lora_name = lora_name
        self.strength_model = strength_model
        self.strength_clip = strength_clip
        self.blocks = blocks_type
        self._loaded_lora = None
    
    def __eq__(self, other):
        return self.lora_name == other.lora_name and self.strength_model == other.strength_model and self.strength_clip == other.strength_clip and self.blocks == other.blocks
    
    def get_lora_path(self):
        return folder_paths.get_full_path("loras", self.lora_name)
        
    def move_resources_from(self, lora_items_by_name):
        existing = lora_items_by_name.get(self.lora_name)
        if existing is not None:
            self._loaded_lora = existing._loaded_lora
            existing._loaded_lora = None

    def apply_lora(self, model, clip):
        if self.is_noop:
            return (model, clip)

        filtered_lora = self.get_filtered_lora()
        
        model_lora, clip_lora = comfy.sd.load_lora_for_models(model, clip, filtered_lora, self.strength_model, self.strength_clip)
        return (model_lora, clip_lora)
    
    def get_filtered_lora(self):
        # Early return if all blocks are present
        if KEY_BLOCKS_ALL in self.blocks:
            return self.lora_object

        # Check if single and double blocks are in the 'self.blocks'
        use_single_blocks = KEY_BLOCKS_SINGLE in self.blocks
        use_single_block_indices = use_single_blocks and len(self.blocks[KEY_BLOCKS_SINGLE]) > 0
        use_double_blocks = KEY_BLOCKS_DOUBLE in self.blocks
        use_double_block_indices = use_double_blocks and len(self.blocks[KEY_BLOCKS_DOUBLE]) > 0

        # Initialize a dictionary to store the filtered Lora values
        filtered_lora = {}

        # Helper function to check for valid indices
        def has_matching_index(layer, index):
            if use_single_block_indices and layer == KEY_BLOCKS_SINGLE:
                return index in self.blocks[KEY_BLOCKS_SINGLE]
            if use_double_block_indices and layer == KEY_BLOCKS_DOUBLE:
                return index in self.blocks[KEY_BLOCKS_DOUBLE]
            return True  # If there are no indices, all are considered matching

        # Iterate through the items in the Lora object
        for key, value in self.lora_object.items():
            components = key.split(".")
            
            try:
                # Strip and lowercase the layer for easier matching
                layer = components[1].strip().lower()
                index = components[2].strip()

                # Check if layer matches and if index is valid
                if use_single_blocks and layer == KEY_BLOCKS_SINGLE:
                    if has_matching_index(layer, index):
                        filtered_lora[key] = value

                if use_double_blocks and layer == KEY_BLOCKS_DOUBLE:
                    if has_matching_index(layer, index):
                        filtered_lora[key] = value
            except:
                pass

        return filtered_lora

    @property
    def lora_object(self):
        if self._loaded_lora is None:
            lora_path = self.get_lora_path()
            if lora_path is None:
                raise ValueError(f"Unable to get file path for lora with name '{self.lora_name}'")
            self._loaded_lora = comfy.utils.load_torch_file(lora_path, safe_load=True)
        
        return self._loaded_lora

    @property
    def is_noop(self):
        return self.strength_model == 0 and self.strength_clip == 0

class LoraTextExtractor:
    def __init__(self):
        self.lora_spec_re = re.compile("(<(?:lora|lyco):[^>]+>)")
        self.selected_loras = SelectedLoras()

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "text": ("STRING", {
                                "multiline": True,
                                "default": ""}),
                            }}

    RETURN_TYPES = ("STRING", "STRING", "LORA_STACK")
    RETURN_NAMES = ("Filtered Text", "Extracted Loras", "Lora Stack")
    FUNCTION = "process_text"
    CATEGORY = "utils"

    def process_text(self, text):
        extracted_loras = "\n".join(self.lora_spec_re.findall(text))
        filtered_text = self.lora_spec_re.sub("", text)

        # the stack format is a list of tuples of full path, model weight, clip weight,
        # e.g. [('styles\\abstract.safetensors', 0.8, 0.8)]
        lora_stack = [(item.get_lora_path(), item.strength_model, item.strength_clip) for item in self.selected_loras.updated_lora_items_with_text(extracted_loras)]
        
        return (filtered_text, extracted_loras, lora_stack)

NODE_CLASS_MAPPINGS = {
    "MultiLoraLoader-70bf3d77": MultiLoraLoader,
    "LoraTextExtractor-b1f83aa2": LoraTextExtractor,
    "MultiLoraParser-8c12fa4b": MultiLoraParser,
    "LoraInfoToHunyuanVidLora-bb8cfde0": LoraInfoToHunyuanVidLora,
    "LoraInfoToWanVidLora-bd47e92c": LoraInfoToWanVidLora,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiLoraLoader-70bf3d77": "MultiLora Loader",
    "LoraTextExtractor-b1f83aa2": "Lora Text Extractor",
    "MultiLoraParser-8c12fa4b": "Multi Lora Parser",
    "LoraInfoToHunyuanVidLora-bb8cfde0": "Lora Info To HunyuanVid Lora",
    "LoraInfoToWanVidLora-bd47e92c": "Lora Info To WanVid Lora",
}
