"""Run ONCE on your own PC to get YT_REFRESH_TOKEN for the channel (you sign in yourself in the browser).

python tools/get_refresh_token.py client_secret.json
Then copy the printed values into the GitHub repository secrets. Never commit client_secret.json.
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], scopes=[
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("YT_CLIENT_ID     =", creds.client_id)
print("YT_CLIENT_SECRET =", creds.client_secret)
print("YT_REFRESH_TOKEN =", creds.refresh_token)
