import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import requests
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from urllib.parse import urlencode
import os
import yaml
from email.mime.image import MIMEImage
# Force TLS 1.2 
class TLS12Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context(ssl_version=ssl.PROTOCOL_TLSv1_2)
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

config_yaml = "config_notifications.yaml"
with open(config_yaml, 'r') as f:
    config_details = yaml.safe_load(f)

def get_current_user_windows_login():
    return "current_user"

def email_coke(html_string, smtp_server,email_ids, time1,attachment_path):
    try:
        user_nm = get_current_user_windows_login()
        smtp_server = smtp_server
        from_address = "CCTV_alerts@mrpl.co.in"
        to_addresses = email_ids
        subject = f"FB7029A/B - Alert Notification at {datetime.now().strftime('%d-%b-%y %H:%M:%S')}"
        body = (f"Dear Sir,\n{html_string} at "
                f"{datetime.now().strftime('%d-%b-%y %H:%M:%S')}")
        msg = MIMEMultipart()
        msg['From'] = from_address
        msg['To'] = ", ".join(to_addresses)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        # image attach 
        with open(attachment_path, 'rb') as f:
            img_data = f.read()
            image = MIMEImage(img_data, name=os.path.basename(attachment_path))
            msg.attach(image)
            
        server = smtplib.SMTP(smtp_server, 25)
        server.ehlo()          

        #server.login(from_address, "password")
        server.sendmail(from_address, to_addresses, msg.as_string())
        server.quit()
        print(f"succcess sent email:")
    except Exception as ex:
        print(f"An error occurred: {ex}")


warnings.simplefilter('ignore', InsecureRequestWarning)

def send_sms(message1, mobile_nos):
    # MSG91 API details
    
    url = "https://api.msg91.com/api/sendhttp.php?country=91"
    
    api_key = "109017A7suZmiLwF56ff6118"  # Replace with actual API key
    
   
    sender_id = "MRPLnf"
   
    dlt_te_id = "1307161745358816689"  # Replace with correct template ID from MSG91 dashboard

     
    # mobile_nos_str = str(mobile_nos)
    
    # mobile_cleaned = ''.join(filter(str.isdigit, mobile_nos_str))
    
    # print("to check the mob num: ",mobile_cleaned)
    # if len(mobile_cleaned) == 10:
    #     # No country code, add 91
    #     mobile_final = mobile_cleaned
    #     print(f"Mobile number detected as 10 digits (without country code): {mobile_final}")
    # elif len(mobile_cleaned) == 12 and mobile_cleaned.startswith('91'):
    #     # Already has country code
    #     mobile_final = mobile_cleaned[2:]  # Remove 91 prefix for API
    #     print(f"Mobile number detected with country code: {mobile_final}")
    # else:
    #     # Use as-is
    #     mobile_final = mobile_cleaned
    #     print(f"Mobile number used as-is: {mobile_final} (length: {len(mobile_final)})")

    # Build the message correctly (matching PowerShell)
    message = f"ALERT - {message1} -MRPL"
    
    # Build the request data
    post_data = {
        "authkey": api_key,
        "mobiles": mobile_nos,
        "message": message,
        "sender": sender_id,
        "route": "4",
        "DLT_TE_ID": dlt_te_id
    }
    try:
        # Create session with TLS 1.2
        session = requests.Session()
        #session.mount('https://', TLS12Adapter())
        
        # Send the request using POST method with TLS 1.2
        # Using data parameter will automatically URL-encode the form data
        print(url)
        response = session.post(url, data=post_data, verify=True, timeout=10)
        
        # Print the response status code
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        print(f"Response encoding: {response.encoding}")
        
        # Parse response for debugging - Check if it's a hex response (success)
        if response.text and all(c in '0123456789abcdefABCDEF' for c in response.text) and len(response.text) > 10:
            print("SMS Send Status: SUCCESS (Hex response indicates successful delivery)")
            print(f"Transaction ID: {response.text}")
        elif "success" in response.text.lower():
            print("SMS Send Status: SUCCESS")
        elif "error" in response.text.lower():
            print("SMS Send Status: FAILED")
        else:
            print("SMS Send Status: UNDEFINED - Response format not recognized")
        
        # Log the response
        with open("log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SMS REQUEST SENT\n")
            log_file.write(f"Mobile Number (Original): {mobile_nos}\n")
            # log_file.write(f"Mobile Number (Final): {mobile_final}\n")
            log_file.write(f"Message: {message}\n")
            log_file.write(f"Sender ID: {sender_id}\n")
            log_file.write(f"API Key: {api_key[:20]}...\n")
            log_file.write(f"DLT Template ID: {dlt_te_id}\n")
            log_file.write(f"DLT Template ID Length: {len(dlt_te_id)} (should be 6-8 digits)\n")
            if len(dlt_te_id) > 10:
                log_file.write(f"WARNING: DLT Template ID looks corrupted - TOO LONG!\n")
            log_file.write(f"Response status code: {response.status_code}\n")
            log_file.write(f"Response text: {response.text}\n")
            log_file.write(f"Response encoding: {response.encoding}\n")
            log_file.write(f"-" * 80 + "\n\n")
       
    except requests.exceptions.RequestException as e:
        print(f"ERROR OCCURRED: {str(e)}")
        with open("log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SMS REQUEST FAILED\n")
            # log_file.write(f"Mobile Number: {mobile_final}\n")
            log_file.write(f"Message: {message}\n")
            log_file.write(f"Error: {str(e)}\n")
            log_file.write(f"-" * 80 + "\n\n")

# Clear log file for fresh testing
with open("log.txt", "w", encoding="utf-8") as f:
   f.write("=== SMS TEST LOG ===\n\n")
# message = config_details["sms"]["message"]
# mobile_numbers = config_details["sms"]["Mobile_numbers"]
# send_sms(message, mobile_numbers)
# html_string = config_details["email"]["message"]
# dtTimestamp1 = datetime.now()
# smtp_server = config_details["email"]["smtp_server"]
# email_ids = config_details["email"]["email_ids"]
# email_coke(html_string,smtp_server, email_ids,dtTimestamp1.strftime("%d-%b-%y"))
