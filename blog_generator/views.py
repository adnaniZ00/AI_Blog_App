from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
import yt_dlp   # Import yt-dlp as youtube_dl
import os
import re
import assemblyai as aai
from .models import BlogPost
import google.generativeai as genai
from django.http import HttpResponseBadRequest
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


# Configure the Gemini API key
genai.configure(api_key=GEMINI_API_KEY)  # Replace with your Gemini API key

# Initialize the model
model = genai.GenerativeModel('gemini-1.5-flash')


@login_required
def index(request):
    if request.method != 'GET':
        return HttpResponseBadRequest("Only GET requests are allowed.")
    return render(request, 'index.html')

@csrf_exempt
@login_required
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data.get('link')
            if not yt_link:
                return JsonResponse({'error': 'YouTube link is required.'}, status=400)
            
            # Get YouTube video details
            video_id = extract_video_id(yt_link)
            video_details = get_video_details(video_id)
            if not video_details:
                return JsonResponse({'error': "Failed to get video details"}, status=500)
            
            title = video_details.get('title')
            if not title:
                return JsonResponse({'error': "Video title not found"}, status=500)
            
            # Get transcription
            transcription = get_transcription(yt_link)
            if not transcription:
                return JsonResponse({'error': "Failed to get transcript"}, status=500)
            
            # Generate blog content from transcription
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': "Failed to generate blog article"}, status=500)
            
            # Save blog article to database
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()
            
            # Return blog article as a response
            return JsonResponse({'content': blog_content})
        
        except Exception as e:
            logger.error(f"Error in generate_blog: {e}")
            return JsonResponse({'error': "Internal server error"}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def extract_video_id(url):
    # Regex to extract the video ID from a YouTube URL
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    return match.group(1) if match else None   

def get_video_details(video_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.videos().list(part='snippet', id=video_id)
    response = request.execute()
    if response['items']:
        return response['items'][0]['snippet']
    return None
    

def sanitize_title(title):
    # Remove special characters and replace spaces with underscores
    title = re.sub(r'[<>:"/\\|?*]', '', title)  # Remove invalid characters
    title = re.sub(r'\s+', ' ', title).strip()  # Normalize spaces
    title = title.replace(' ', '_')  # Replace spaces with underscores
    return title
    

# def download_audio(link):
#     # Extract YouTube video info
#     with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': settings.YOUTUBE_COOKIES_FILE}) as ydl:
#         info_dict = ydl.extract_info(link, download=False)
#         title = info_dict.get('title', 'audio')
#         sanitized_title = sanitize_title(title)

#     # Update options for yt-dlp
#     ydl_opts = {
#         'format': 'bestaudio/best',
#         'outtmpl': os.path.join(settings.MEDIA_ROOT, f'{sanitized_title}.%(ext)s'),
#         'postprocessors': [{
#             'key': 'FFmpegExtractAudio',
#             'preferredcodec': 'mp3',
#             'preferredquality': '192',
#         }],
#         'ffmpeg_location': 'C:/ProgramData/chocolatey/bin',  # Adjust path if necessary
#     }
    
#     # Download the audio
#     with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#         ydl.download([link])
#         return os.path.join(settings.MEDIA_ROOT, f"{sanitized_title}.mp3")

def download_audio(link):
    # Extract YouTube video info
    with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': settings.YOUTUBE_COOKIES_FILE}) as ydl:
        info_dict = ydl.extract_info(link, download=False)
        title = info_dict.get('title', 'audio')
        sanitized_title = sanitize_title(title)

    # Use a temporary directory instead of MEDIA_ROOT
    temp_dir = '/tmp'
    audio_path = os.path.join(temp_dir, f'{sanitized_title}.mp3')

    # Update options for yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(temp_dir, f'{sanitized_title}.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    # Download the audio
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([link])
        return audio_path # Return the full path to the temporary file
        

def get_transcription(link):
        try:
            audio_file = download_audio(link)
            if not audio_file:
                raise Exception("Failed to download audio.")
            
            aai.settings.api_key = ASSEMBLYAI_API_KEY
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_file)
            
            if not transcript or not transcript.text:
                raise Exception("Transcription failed or returned empty.")
            
            return transcript.text
    
        except Exception as e:
            logger.error(f"Error in get_transcription: {e}")
            return None
        

def generate_blog_from_transcription(transcription):
        try:
            # Set up the prompt for Generative AI
            prompt = (
                f"Based on the following transcript from a YouTube video, write a comprehensive blog article. "
                f"The content should be well-structured and engaging, avoiding a direct YouTube video tone:\n\n{transcription}\n\nArticle:"
            )
            
            # Call the Generative API to generate blog content
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1000,  # Adjust as needed
                    temperature=0.7  # Adjust for more creativity or coherence
                )
            )
            
            if not response or not response.text:
                raise Exception("Failed to generate content or received empty response.")
            
            return response.text.strip()
    
        except Exception as e:
            logger.error(f"Error in generate_blog_from_transcription: {e}")
            return None

@login_required
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

@login_required
def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('blog-list')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('index')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
        
    return render(request, 'signup.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')


