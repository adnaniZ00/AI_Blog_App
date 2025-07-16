
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import os
from .models import BlogPost
import google.generativeai as genai
from django.http import HttpResponseBadRequest
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
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
            # We now expect 'title' and 'transcript' from the front-end
            title = data.get('title')
            transcript = data.get('transcript')
            yt_link = data.get('link', 'N/A') # Get optional link

            if not transcript:
                return JsonResponse({'error': 'A transcript text is required.'}, status=400)
            
            # If title is not provided, generate it
            if not title:
                logger.info("Generating title from transcript...")
                title_prompt = f"Based on the following transcript, generate a concise and compelling blog post title. The title should be no more than 10 words. Do not add quotation marks.\n\nTranscript: {transcript}\n\nTitle:"
                title_response = model.generate_content(title_prompt)
                title = title_response.text.strip().replace('"', '')
                logger.info(f"Generated title: {title}")
            
            blog_content = generate_blog_from_transcription(transcript)
            if not blog_content:
                return JsonResponse({'error': "Failed to generate blog article from transcript."}, status=500)
            
            # Save the new blog post
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()
            
            return JsonResponse({'content': blog_content})
        
        except Exception as e:
            logger.error(f"Error in generate_blog view: {e}")
            return JsonResponse({'error': "An internal server error occurred."}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def generate_blog_from_transcription(transcription):
    try:
        prompt = (
            f"Based on the following transcript, write a comprehensive and well-structured blog article. "
            f"The content should be engaging and easy to read. Avoid a direct conversational tone.\n\nTranscript: {transcription}\n\nArticle:"
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2048,
                temperature=0.7
            )
        )
        if not response or not response.text:
            raise Exception("Failed to generate content or received empty response.")
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in generate_blog_from_transcription: {e}")
        return None

# ... (All other views like login, signup, blog_list etc. remain the same)
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

