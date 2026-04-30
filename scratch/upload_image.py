import requests

def upload_to_catbox(file_path):
    url = "https://catbox.moe/user/api.php"
    data = {
        "reqtype": "fileupload",
    }
    with open(file_path, "rb") as f:
        files = {"fileToUpload": f}
        response = requests.post(url, data=data, files=files)
        return response.text

if __name__ == "__main__":
    file_path = r"C:\Users\Anirudh\.gemini\antigravity\brain\5e1fd095-1132-4c8e-af57-4a91104f3028\media__1777555954629.png"
    try:
        url = upload_to_catbox(file_path)
        print(f"Uploaded URL: {url}")
    except Exception as e:
        print(f"Error: {e}")
