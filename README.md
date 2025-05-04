```
title: Artificer v1 - IKEA Product Image and Measurements Extractor
emoji: 🛋️
colorFrom: blue
colorTo: yellow
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
short_description: Artificer's version 1 is a Gradio-based web application that extracts product images, measurements, and materials information from IKEA product pages.
pinned: true
license: mit
```

# 🛋️ Artificer: Image-to-blueprints generation for woodworking projects

Artificer's phase 1 is a Gradio-based web application that extracts product images, measurements, and materials information from IKEA product pages.

## Features

- Extract high-resolution product images
- Get detailed product measurements
- Extract materials information
- Easy-to-use web interface
- Works with any IKEA product URL

## Demo

You can try the live demo on Hugging Face Spaces: [Artificer Demo](https://huggingface.co/spaces/RSHVR/Ikea-Extraction)


## Usage

1. Paste an IKEA product URL into the input field
2. Click "Extract Product Data"
3. View the extracted images, measurements, and materials information

## Development

The application is built with:
- Gradio 4.0+ for the web interface
- BeautifulSoup4 for HTML parsing
- Requests for fetching web pages
- Python 3.12+

## Hugging Face Spaces

To deploy this application on Hugging Face Spaces, the repository includes a `spaces.yml` configuration file that sets up the environment and dependencies. Copy the contents of this file and paste them at the top of your README.md file.

## License

[MIT License](LICENSE)