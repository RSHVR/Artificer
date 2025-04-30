import gradio as gr
import requests

API_URL = "http://localhost:8000/extract"

def get_product_data_from_url(url):
    """
    Retrieve product data (images, measurements, materials) from the API.
    
    Args:
        url: Product URL to extract data from
        
    Returns:
        Tuple of (image_list, measurements_str, materials_str)
    """
    try:
        payload = {
            "url": url,
            "download_images": False
        }

        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract images
        images = [img["url"] for img in data.get("images", {}).values()]
        
        # Format measurements into markdown
        measurements = data.get("measurements", {})
        if measurements:
            measurements_str = "\n".join([f"- **{k.title()}**: {v}" for k, v in measurements.items()])
        else:
            measurements_str = "No measurements found."
            
        # Format materials into markdown
        materials = data.get("materials", {})
        if materials:
            materials_str = "\n".join([f"- **{k.title()}**: {v}" for k, v in materials.items()])
        else:
            materials_str = "No materials information found."

        return images, measurements_str, materials_str

    except Exception as e:
        error_message = f"Error: {str(e)}"
        return [], error_message, error_message

def create_interface():
    """Create and configure the Gradio interface"""
    with gr.Blocks(title="IKEA Product Image + Measurement Extractor") as demo:
        gr.Markdown("## IKEA Product Image + Measurement Extractor")
        gr.Markdown("Enter an IKEA product URL to extract images, measurements, and materials information.")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Input section
                url_input = gr.Textbox(
                    label="Product URL", 
                    placeholder="https://www.ikea.com/product/...",
                    info="Paste IKEA product URL here"
                )
                submit_btn = gr.Button("Extract Product Data", variant="primary")
                
                # Results section - Measurements and Materials
                with gr.Accordion("Product Information", open=True):
                    measurements_display = gr.Markdown(label="Measurements")
                    materials_display = gr.Markdown(label="Materials")
                    
            with gr.Column(scale=2):
                # Gallery component for displaying images
                image_gallery = gr.Gallery(
                    label="Product Images",
                    show_label=True,
                    columns=2,
                    height=500,
                    object_fit="contain"
                )

        # Set up the click event
        submit_btn.click(
            fn=get_product_data_from_url,
            inputs=url_input,
            outputs=[image_gallery, measurements_display, materials_display]
        )
        
    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch(share=False)