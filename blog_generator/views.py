
# from django.shortcuts import render, redirect
# from django.contrib.auth.models import User
# from django.contrib.auth import authenticate, login, logout
# from django.contrib.auth.decorators import login_required
# from django.views.decorators.csrf import csrf_exempt
# from django.http import JsonResponse
# import json
# import os
# from .models import BlogPost
# import google.generativeai as genai
# from django.http import HttpResponseBadRequest
# import logging

# logger = logging.getLogger(__name__)

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# genai.configure(api_key=GEMINI_API_KEY)
# model = genai.GenerativeModel('gemini-2.5-flash')


# @login_required
# def index(request):
#     if request.method != 'GET':
#         return HttpResponseBadRequest("Only GET requests are allowed.")
#     return render(request, 'index.html')

# @csrf_exempt
# @login_required
# def generate_blog(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             # We now expect 'title' and 'transcript' from the front-end
#             title = data.get('title')
#             transcript = data.get('transcript')
#             yt_link = data.get('link', 'N/A') # Get optional link

#             if not transcript:
#                 return JsonResponse({'error': 'A transcript text is required.'}, status=400)
            
#             # If title is not provided, generate it
#             if not title:
#                 logger.info("Generating title from transcript...")
#                 title_prompt = f"Based on the following transcript, generate a concise and compelling blog post title. The title should be no more than 10 words. Do not add quotation marks.\n\nTranscript: {transcript}\n\nTitle:"
#                 title_response = model.generate_content(title_prompt)
#                 title = title_response.text.strip().replace('"', '')
#                 logger.info(f"Generated title: {title}")
            
#             blog_content = generate_blog_from_transcription(transcript)
#             if not blog_content:
#                 return JsonResponse({'error': "Failed to generate blog article from transcript."}, status=500)
            
#             # Save the new blog post
#             new_blog_article = BlogPost.objects.create(
#                 user=request.user,
#                 youtube_title=title,
#                 youtube_link=yt_link,
#                 generated_content=blog_content,
#             )
#             new_blog_article.save()
            
#             return JsonResponse({'content': blog_content})
        
#         except Exception as e:
#             logger.error(f"Error in generate_blog view: {e}")
#             return JsonResponse({'error': "An internal server error occurred."}, status=500)
#     else:
#         return JsonResponse({'error': 'Invalid request method'}, status=405)


# def generate_blog_from_transcription(transcription):
#     try:
#         prompt = (
#             f"Based on the following transcript, write a comprehensive and well-structured blog article. "
#             f"The content should be engaging and easy to read. Avoid a direct conversational tone.\n\nTranscript: {transcription}\n\nArticle:"
#         )
#         response = model.generate_content(
#             prompt,
#             generation_config=genai.types.GenerationConfig(
#                 max_output_tokens=2048,
#                 temperature=0.7
#             )
#         )
#         if not response or not response.text:
#             raise Exception("Failed to generate content or received empty response.")
#         return response.text.strip()
#     except Exception as e:
#         logger.error(f"Error in generate_blog_from_transcription: {e}")
#         return None

# # ... (All other views like login, signup, blog_list etc. remain the same)
# @login_required
# def blog_list(request):
#     blog_articles = BlogPost.objects.filter(user=request.user)
#     return render(request, "all-blogs.html", {'blog_articles': blog_articles})

# @login_required
# def blog_details(request, pk):
#     blog_article_detail = BlogPost.objects.get(id=pk)
#     if request.user == blog_article_detail.user:
#         return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
#     else:
#         return redirect('blog-list')

# def user_login(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             login(request, user)
#             return redirect('index')
#         else:
#             error_message = "Invalid username or password"
#             return render(request, 'login.html', {'error_message': error_message})
#     return render(request, 'login.html')

# def user_signup(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         email = request.POST['email']
#         password = request.POST['password']
#         repeatPassword = request.POST['repeatPassword']
#         if password == repeatPassword:
#             try:
#                 user = User.objects.create_user(username, email, password)
#                 user.save()
#                 login(request, user)
#                 return redirect('index')
#             except:
#                 error_message = 'Error creating account'
#                 return render(request, 'signup.html', {'error_message':error_message})
#         else:
#             error_message = 'Password do not match'
#             return render(request, 'signup.html', {'error_message':error_message})
#     return render(request, 'signup.html')

# @login_required
# def user_logout(request):
#     logout(request)
#     return redirect('login')



from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.db import IntegrityError
import json
import os
import logging
from .models import BlogPost
import google.generativeai as genai

# Set up logging
logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
# It's good practice to handle the case where the API key might be missing.
try:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    logger.error(f"Failed to configure Generative AI: {e}")
    model = None # Set model to None if configuration fails

# --- Core Views ---

@login_required
def index(request):
    """
    Renders the main page for generating blogs.
    """
    if request.method != 'GET':
        return HttpResponseBadRequest("Only GET requests are allowed.")
    return render(request, 'index.html')

@login_required
def generate_blog(request):
    """
    Handles the POST request to generate a blog from a transcript using a single API call.
    This view is now secure and expects a CSRF token from the frontend.
    """
    if model is None:
        return JsonResponse({'error': 'AI model is not configured. Please check server logs.'}, status=500)
        
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    try:
        data = json.loads(request.body)
        title = data.get('title')
        transcript = data.get('transcript')
        yt_link = data.get('link', 'N/A')

        if not transcript:
            return JsonResponse({'error': 'A transcript is required.'}, status=400)

        logger.info("Generating title and content in a single API call...")
        
        # A single, powerful prompt asking for both parts separated by a unique delimiter.
        combined_prompt = (
            f"Based on the following transcript, perform two tasks:\n"
            f"1. Generate a concise and compelling blog post title (no more than 10 words, no quotes).\n"
            f"2. Write a comprehensive and well-structured blog article.\n\n"
            f"Separate the title and the article with the special delimiter '---CONTENT---'.\n\n"
            f"Transcript: {transcript}\n\n"
            f"Title and Article:"
        )
        
        response = model.generate_content(combined_prompt)
        full_text = response.text.strip()
        
        # Split the response to get the title and content.
        if '---CONTENT---' in full_text:
            generated_title, generated_content = full_text.split('---CONTENT---', 1)
            # Use the title provided by the user if it exists, otherwise use the generated one.
            final_title = title if title else generated_title.strip()
            final_content = generated_content.strip()
        else:
            # Fallback in case the model doesn't follow instructions perfectly.
            logger.warning("Delimiter '---CONTENT---' not found in AI response. Using fallback.")
            final_title = title if title else "A Blog Post About Your Video"
            final_content = full_text

        # BlogPost.objects.create() creates and saves the object in one step.
        BlogPost.objects.create(
            user=request.user,
            youtube_title=final_title,
            youtube_link=yt_link,
            generated_content=final_content,
        )
        
        return JsonResponse({'title': final_title, 'content': final_content})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body.'}, status=400)
    except Exception as e:
        logger.error(f"Error in generate_blog view: {e}")
        return JsonResponse({'error': "An internal server error occurred while generating the blog."}, status=500)


# --- Blog Post Management Views ---

@login_required
def blog_list(request):
    """
    Displays a list of all blog posts created by the logged-in user.
    """
    blog_articles = BlogPost.objects.filter(user=request.user).order_by('-created_at')
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

@login_required
def blog_details(request, pk):
    """
    Displays the details of a specific blog post, ensuring the user owns it.
    """
    try:
        blog_article_detail = BlogPost.objects.get(id=pk)
        if request.user == blog_article_detail.user:
            return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
        else:
            # If the user doesn't own the blog, redirect them to their list.
            return redirect('blog_list')
    except BlogPost.DoesNotExist:
        return redirect('blog_list')


# --- User Authentication Views ---

def user_login(request):
    """
    Handles user login.
    """
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            error_message = "Invalid username or password. Please try again."
            return render(request, 'login.html', {'error_message': error_message})
    return render(request, 'login.html')

def user_signup(request):
    """
    Handles new user registration with improved error handling.
    """
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        repeatPassword = request.POST.get('repeatPassword')

        if password != repeatPassword:
            error_message = 'Passwords do not match.'
            return render(request, 'signup.html', {'error_message': error_message})
        
        if User.objects.filter(username=username).exists():
            error_message = 'That username is already taken. Please choose another.'
            return render(request, 'signup.html', {'error_message': error_message})
        
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect('index')
        except IntegrityError:
            error_message = 'An account with that email already exists.'
            return render(request, 'signup.html', {'error_message': error_message})
        except Exception as e:
            logger.error(f"An unexpected error occurred during signup: {e}")
            error_message = 'An unexpected error occurred. Please try again.'
            return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')

@login_required
def user_logout(request):
    """
    Logs the user out and redirects to the login page.
    """
    logout(request)
    return redirect('login')