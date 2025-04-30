from gradio_client import Client


url = "https://www.ikea.com/ca/en/p/hammaroen-pergola-gray-beige-dark-gray-beige-20549239/"

client = Client("RSHVR/Ikea-Extraction")
result = client.predict(
		url=url,
		api_name="/get_product_data_from_url"
)
print(result)