# ComfyUI Coziness

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI).

- [MultiLora Loader](#multilora-loader): Uses a textual description of loras to add to a model
- [Lora Text Extractor](#lora-text-extractor): Takes text, such as a prompt, and filters out lora descriptions. You can connect the filtered text to CLIP Text Encode and the extracted loras to MultiLora Loader.

## Installing

Two options:

- Add [MultiLoraLoader.py](MultiLoraLoader.py) to ComfyUI's `custom_nodes` directory.
- Clone this repo into the `custom_nodes` directory, which will make it easier to update.
   1. `cd custom_nodes`
   2. `git clone https://github.com/skfoo/ComfyUI-Coziness.git`

Then restart ComfyUI.

## Updates

### 2024/2/22
- Added support for connecting Lora Text Extractor directly to *Efficiency Nodes for ComfyUI*'s lora stack inputs

### 2024/5/27
- v1.0.2: Updates for Comfy Registry

## MultiLora Loader

Uses a textual description to specify the loras you want to add to a checkpoint model.

![Example MultiLora Loader Connections](/docs/images/multilora-loader-connections.png)

You can add the node from the `loaders` category at `loaders > MultiLora Loader`.

Connect the inputs & outputs like you would with the normal ComfyUI lora nodes. In the text box, type the loras you want to use, each on one line. The format is:

`file_name[:weight1[:weight2]]`

If you specify only one weight, it used for both model and clip. If you specify two, the first weight is for the model and the second is for the clip. If you specify none, it uses 1 for both.

There's two ways to specify each file name. If your Lora directory has the following contents,

```
- one.safetensors
- Some Folder
  - two.safetensors
```

You can use either the full subpath, like `Some Folder/two.safetensors`, or just the file name itself, like `two`.

Also, to make copy & pasting Automatic1111 prompts easy, it accepts names wrapped in `<lora:..>` or `<lyco:...>`. It doesn't make a difference if you use lora or lyco, the stuff is completely ignored.

You can also use `#` to start a comment.

Here's an example loading six loras with each form,

```
one
Some Folder/two.safetensors:1.1
three:1
four:1:0.5
<lora:five> # this is a comment
<lyco:six:0.8:0.7>
# <lora:nope> this isn't loaded because it's commented out
```

## Lora Text Extractor

Takes the input text and extracts loras specified using Automatic1111's lora syntax out of it. It has two outputs: one for the filtered text without the loras, and another with the stuff that was removed from it, separated by newlines. You can connect the filtered text output to a CLIP Text Encode node to use as your prompt, and the lora text output to MultiLora Loader. If you're using Efficiency Nodes for ComfyUI, you can connect the Lora Stack output to Efficient Loader's lora_stack input.

![Example Lora Text Extractor Connections](/docs/images/lora-text-extractor-connections.png)

You can add the node from the `utils` category at `utils > Lora Text Extractor`.

In order to connect to those nodes, you have to convert their text boxes into inputs. Right-click on each node (CLIP Text Encode and MultiLora Loader) and select "Convert text to input" from the menu.

![Context Menu for a node with 'Convert text to input' selected](/docs/images/convert-to-input.png)

### Example Input & Outputs

#### Input

```
pizza <lora:add_detail:0.5>,<lora:epi_noiseoffset2:1.1>,
```

#### Outputs

###### Filtered Text
```
pizza ,,
```
###### Extracted Loras
```
<lora:add_detail:0.5>
<lora:epi_noiseoffset2:1.1>
```