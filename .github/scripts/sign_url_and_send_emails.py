import os
import base64
import json
import pickle
import re
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64


from google.auth import credentials
from google.cloud import storage
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError
import datetime


def decode_and_save_token(encoded_token, output_file_path):
    try:
        # Decode the base64-encoded token
        decoded_token = base64.b64decode(encoded_token)
        
        # Write the decoded token to a file
        with open(output_file_path, 'wb') as output_file:
            output_file.write(decoded_token)
        
        print(f"Decoded token successfully saved to {output_file_path}")
    except Exception as e:
        print(f"Error occurred while decoding the token and saving it to a file: {e}")


# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate_gmail_api():
    """Authenticate and return the Gmail API service."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    encoded_token = os.getenv('TOKEN_PICKLE')
    output_file_path = "token.pickle"  # File where the decoded token will be saved
    decode_and_save_token(encoded_token, output_file_path)
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        # Build the Gmail API client
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as error:
        print(f'An error occurred: {error}')
        return None

def create_message(sender, to, subject, body):
    """Create an email message."""
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(body)
    message.attach(msg)
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}


def send_email(service, sender, to, subject, body):
    """Send an email message using the Gmail API."""
    try:
        # Create the MIME message
        message = MIMEMultipart()
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject
        
        # Attach the HTML body as MIMEText (HTML content type)
        msg = MIMEText(body, 'html')  # Specify the MIME type as 'html'
        message.attach(msg)
        
        # Encode the message as base64 URL-safe format
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Send the message using the Gmail API
        sent_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
        print(f"Message sent! Message ID: {sent_message['id']}")
    except HttpError as error:
        print(f"An error occurred: {error}")


def generate_signed_url(bucket_name, object_name):
    try:
        # Get the service account JSON from the GitHub secret (as environment variable)
        service_account_json = os.getenv('GCP_SERVICE_ACCOUNT_KEY')

        if not service_account_json:
            raise ValueError("Service account key is not set in environment variables.")

        # Parse the JSON from the environment variable
        credentials_info = json.loads(service_account_json)

        # Load the credentials from the parsed JSON
        credentials = service_account.Credentials.from_service_account_info(credentials_info)

        # Initialize Google Cloud Storage client with the loaded credentials
        storage_client = storage.Client(credentials=credentials, project=credentials.project_id)

        # Get the bucket
        bucket = storage_client.bucket(bucket_name)

        # Get the blob (file in GCS)
        blob = bucket.blob(object_name)
        # Generate a signed URL for the object
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(days=7),  # Set the expiration time (e.g., 7 days)
            method='GET',  # Specify the HTTP method (e.g., GET for download)
        )
        
        return url
        

    except DefaultCredentialsError as e:
        print(f"Error: Unable to authenticate with Google Cloud. {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def generate_html_body(urls):
    # Create the HTML body
    html_template = """
    <html>
    <head>
        <title>Archived Files Retrieval</title>
    </head>
    <body>
        <p>Hello,</p>

        <p>This is an automated email. Below, you will find signed URLs to retrieve your archived files. Please note that these links are valid for 7 days.</p>

        <p><strong>Link to Archived Files:</strong></p>
        <ul>
    """

    # Loop through the URLs and add them to the HTML
    for url in urls:
        html_template += f"<li><a href='{url}' target='_blank'>{url}</a></li>"

    # Close the HTML tags
    html_template += """
        </ul>

        <p><strong>Action Required:</strong><br>
        Download your files before the links expire.<br>
        If you do not retrieve your files within 7 days, you will need to submit a new <a href="https://github.com/berkeley-dsep-infra/datahub/issues/new?template=data_archival_request.yml" target="_blank">GitHub Issue</a> to retrieve your files. To do so:</p>

        <ul>
            <li>Open a new GitHub issue using the unique URL found in the WHERE-ARE-MY-FILES.txt file.</li>
            <li>Ensure that you have included both the UC Berkeley email address and the link to your DataHub folder, which should follow this format: <code>gs://ucb-datahub-archived-homedirs/semester-archived/hub-url/calnet-id.tar.gz</code></li>
        </ul>

        <p><strong>Steps to Extract Your Archived Files:</strong><br>
        If you need help extracting the downloaded .tar file, please read below: (This information is targeted for users using Windows 11 or earlier versions).</p>

        <p><strong>What is a .tar file?</strong><br>
        A .tar file is a type of compressed file that holds many other files inside it, kind of like a folder zipped into one file. To access the files inside, you need to "untar" (or extract) them.</p>

        <p><strong>Steps to Untar a .tar File:</strong></p>

        <ol>
            <li><strong>Download the .tar File:</strong> When you click on the shared link, you will be downloading a .tar file to your device. It could look something like <code>your-calnet-id.tar</code>.</li>
            <li><strong>Open the Terminal (Command Line):</strong> You need to either use the "Terminal" (on Mac/Linux) or "Command Prompt" (on Windows) to untar the file.</li>
            <ul>
                <li><strong>On Windows:</strong> If you don't have a program like 7-Zip, you can install it first.</li>
                <li><strong>On Mac/Linux:</strong> The Terminal is already available, so you can open it from your Applications folder (Mac) or search for it in your app list (Linux).</li>
            </ul>
            <li><strong>Navigate to the Folder with the .tar File:</strong> Locate the .tar file. In Terminal or Command Prompt, use the <code>cd</code> command to navigate to the folder containing the file.</li>
            <li><strong>Run the Command to Untar:</strong> Once you're in the right folder, type the following command to untar the file:</li>
            <ul>
                <li><strong>On Mac/Linux:</strong> Type this command in the Terminal:
                    <pre><code>tar -xvf your-calnet-id.tar</code></pre>
                </li>
                <li><strong>On Windows:</strong> If you are using 7-Zip, right-click the .tar file, then choose <strong>7-Zip > Extract Here</strong>. This will extract the files in the same location.</li>
            </ul>
            <li><strong>Find Your Extracted Files:</strong> After the command runs (or you extract with 7-Zip), you should see a new folder (or a bunch of new files) appear. These are your files from DataHub that were inside the .tar archive.</li>
        </ol>

        <p>Best,</p>

        <p><strong>DataHub Support Team</strong></p>
    </body>
    </html>
    """

    return html_template


def parse_issue_url(issue_url):
    """Parse GitHub issue URL to extract owner, repo, and issue number."""
    # Pattern: https://github.com/owner/repo/issues/123
    pattern = r'https://github\.com/([^/]+)/([^/]+)/issues/(\d+)'
    match = re.match(pattern, issue_url)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None


def redact_email_from_issue(issue_url, github_token):
    """Redact email address from GitHub issue for FERPA compliance."""
    try:
        owner, repo, issue_number = parse_issue_url(issue_url)
        if not all([owner, repo, issue_number]):
            print("Error: Could not parse issue URL")
            return False
        
        # GitHub API endpoint
        api_url = f'https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}'
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get current issue details
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching issue: {response.status_code}")
            return False
        
        issue_data = response.json()
        current_body = issue_data.get('body', '')
        
        # Redact email addresses from the body
        # Pattern to match email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        redacted_body = re.sub(email_pattern, '[REDACTED FOR FERPA COMPLIANCE]', current_body)
        
        # Update the issue with redacted body
        update_data = {'body': redacted_body}
        update_response = requests.patch(api_url, headers=headers, json=update_data)
        
        if update_response.status_code == 200:
            print(f"Successfully redacted email from issue #{issue_number}")
            return True
        else:
            print(f"Error updating issue: {update_response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error redacting email from issue: {e}")
        return False


def add_issue_comment(issue_url, github_token, comment_text):
    """Add a comment to the GitHub issue."""
    try:
        owner, repo, issue_number = parse_issue_url(issue_url)
        if not all([owner, repo, issue_number]):
            print("Error: Could not parse issue URL")
            return False
        
        # GitHub API endpoint for comments
        api_url = f'https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments'
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Create comment
        comment_data = {'body': comment_text}
        response = requests.post(api_url, headers=headers, json=comment_data)
        
        if response.status_code == 201:
            print(f"Successfully added comment to issue #{issue_number}")
            return True
        else:
            print(f"Error adding comment: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error adding comment to issue: {e}")
        return False



if __name__ == '__main__':
    # Sign URLs
    extracted_link = os.getenv('EXTRACTED_LINK')
    all_links = extracted_link.split(',')
    results = []
    for link in all_links:
        # Your bucket and object details
        bucket_name = link.split('//')[1].split('/')[0]
        object_name = '/'.join(link.split('//')[1].split('/')[1:])

        # Generate signed URL
        url = generate_signed_url(bucket_name, object_name)
        results.append(url)


    # Authenticate and build the Gmail API service
    service = authenticate_gmail_api()
    issue_url = os.getenv('ISSUE_URL')
    github_token = os.getenv('GITHUB_TOKEN')
    
    if service:
        sender = 'datahub-dataretrieval@berkeley.edu'  # Replace with your email address
        recipient = os.getenv('RECEIVER_EMAIL')  # Replace with recipient's email
        subject = 'Access Your Archived Files from DataHub (Valid for 7 Days)'
        

        html_body = generate_html_body(results)


        # Send the email
        send_email(service, sender, recipient, subject, html_body)
        
        # After successful email sending, redact email from GitHub issue and add comment
        if issue_url and github_token:
            print("\nProcessing GitHub issue for FERPA compliance...")
            
            # Redact email address from the issue
            redaction_success = redact_email_from_issue(issue_url, github_token)
            
            # Add comment to the issue
            comment_text = "Access Your Archived Files from DataHub (Valid for 7 Days). Your email id is deleted for FERPA purposes."
            comment_success = add_issue_comment(issue_url, github_token, comment_text)
            
            if redaction_success and comment_success:
                print("Successfully completed FERPA compliance steps for GitHub issue.")
            else:
                print("Warning: Some FERPA compliance steps may have failed. Check logs above.")
        else:
            print("Warning: ISSUE_URL or GITHUB_TOKEN not found. Skipping GitHub issue updates.")