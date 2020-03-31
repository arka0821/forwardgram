from telethon import TelegramClient, events
from telethon.tl.types import InputChannel
import yaml
import sys
import logging
from telethon.utils import is_image
import pytesseract
import re
import time 
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(level=logging.WARNING)
logger = logging.getLogger(__name__)

def start(config):
    pytesseract.pytesseract.tesseract_cmd = config['tesseract_path']
    client = TelegramClient(config["session_name"], 
                            config["api_id"], 
                            config["api_hash"])
    client.start()

    input_channels_entities = []
    output_channel_entity = None
    for d in client.iter_dialogs():
        if d.name in config["input_channel_names"]:
            input_channels_entities.append(InputChannel(d.entity.id, d.entity.access_hash))
        if d.name == config["output_channel_name"]:
            output_channel_entity = InputChannel(d.entity.id, d.entity.access_hash)
            
    if output_channel_entity is None:
        logger.error(f"Could not find the channel \"{config['output_channel_name']}\" in the user's dialogs")
        sys.exit(1)
    logging.info(f"Listening on {len(input_channels_entities)} channels. Forwarding messages to {config['output_channel_name']}.")
    
    @client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):        
        message_text = None
        text_in_image = None
        if event.message.media is not None:
            if is_image(event.message.media):
                await client.download_media(event.message.media, config["temp_path"] + 'temp.jpg')
                time.sleep(2)
                # Get HOCR output
                hocr = pytesseract.image_to_pdf_or_hocr(config["temp_path"] + 'temp.jpg', extension='hocr')
                soup = BeautifulSoup(hocr.decode('utf-8'), 'html.parser')
                elements = soup.find_all("span", class_="ocrx_word")
                text = ''
                for elm in elements:
                    text += elm.text            
                text_in_image = re.findall(r'[A-Z]{3}\s*/\s*[A-Z]{3}', text)
                if len(text_in_image) > 0:
                    text_in_image = "Symbol: " + text_in_image[0].replace('/','').replace(" ","")
                    message_from_sender = parese_message(event.message.message)
                    if message_from_sender is not None and text_in_image is not None:
                        message_text = text_in_image + "\n" + message_from_sender
                    elif text_in_image is None:
                        message_text = message_from_sender
                    elif message_from_sender is None:
                        message_text = text_in_image            
                    await client.send_message(output_channel_entity, message_text)    
    client.run_until_disconnected()
    
def parese_message(message):
    if message is not None or len(message) <1:
        parsed_message = "Type: {x[0]}\nStart: {x[1]}\nTP1: {x[3]}\nTP2: {x[5]}\nTP3: {x[7]}\nSL: {x[9]}".format(x=message.split())
    else:
        parsed_message = None    
    return parsed_message 

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} CONFIG_PATH")
        sys.exit(1)
    with open(sys.argv[1], 'rb') as f:
        config = yaml.load(f)
    start(config)
