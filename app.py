from flask import Flask, render_template, request, send_from_directory
from gtts import gTTS
# MoviePy imports:
from moviepy.video.VideoClip import TextClip # For creating text visuals
from moviepy.audio.io.AudioFileClip import AudioFileClip # For reading audio duration and content
# Note: CompositeVideoClip is not explicitly imported as TextClip.set_audio handles composition.
# Note: VideoFileClip is not imported as we are not reading existing video files.
# Note: change_settings and its related logic are removed. ImageMagick must be in PATH.
import os

app = Flask(__name__)

static_dir = 'static'
audio_dir = os.path.join(static_dir, 'audio')
video_dir = os.path.join(static_dir, 'videos')

for directory in [static_dir, audio_dir, video_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)

app.config['UPLOAD_FOLDER'] = audio_dir
app.config['GENERATED_VIDEO_FOLDER'] = video_dir

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_video', methods=['POST'])
def generate_video():
    script = request.form.get('script')
    audio_file = request.files.get('audioFile')

    audio_path = None
    audio_duration = 0
    audio_clip_for_duration = None # To store clip for getting duration
    audio_clip_for_composition = None # To store clip for video composition

    if audio_file and audio_file.filename != '':
        filename = "uploaded_" + os.path.basename(audio_file.filename)
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(audio_path)
        try:
            # Use AudioFileClip for uploaded audio
            audio_clip_for_duration = AudioFileClip(audio_path)
            audio_duration = audio_clip_for_duration.duration
        except Exception as e:
            print(f"Error processing uploaded audio '{audio_path}': {e}")
            if audio_clip_for_duration: audio_clip_for_duration.close()
            return f"Error processing uploaded audio file: {str(e)}", 500 # Return string representation of e

    elif script:
        filename = "script_audio.mp3"
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            tts = gTTS(text=script, lang='en')
            tts.save(audio_path)
            # Use AudioFileClip for TTS audio
            audio_clip_for_duration = AudioFileClip(audio_path)
            audio_duration = audio_clip_for_duration.duration
        except Exception as e:
            print(f"Error generating TTS audio '{audio_path}': {e}")
            if audio_clip_for_duration: audio_clip_for_duration.close()
            return f"Error generating audio from script: {str(e)}", 500 # Return string representation of e
    else:
        return "No script or audio file provided.", 400

    if not audio_path or audio_duration == 0:
        if audio_clip_for_duration: audio_clip_for_duration.close() # Close if it was opened
        return "Audio processing failed or audio duration is zero.", 500

    # If audio_clip_for_duration was successfully used, we can close it now
    # as a new one will be created for composition.
    if audio_clip_for_duration:
        audio_clip_for_duration.close()
        audio_clip_for_duration = None


    txt_clip_resource = None
    # final_clip_resource is not strictly needed as a variable if we only use it to call write_videofile
    # However, TextClip.set_audio returns the TextClip itself, modified. So txt_clip_resource becomes the final clip.
    try:
        txt_clip_resource = TextClip(script, font_size=30, color='white', bg_color='black', size=(640, 480), method='caption')
        txt_clip_resource = txt_clip_resource.set_duration(audio_duration)
        txt_clip_resource = txt_clip_resource.set_pos('center')

        # Create a new AudioFileClip instance for the composition.
        audio_clip_for_composition = AudioFileClip(audio_path)
        # set_audio modifies txt_clip_resource in place and returns it.
        txt_clip_resource = txt_clip_resource.set_audio(audio_clip_for_composition)

        video_filename = "generated_video.mp4"
        video_output_path = os.path.join(app.config['GENERATED_VIDEO_FOLDER'], video_filename)

        txt_clip_resource.write_videofile(video_output_path, codec="libx264", audio_codec="aac", fps=24, logger=None)

        return send_from_directory(app.config['GENERATED_VIDEO_FOLDER'], video_filename, as_attachment=True)

    except Exception as e:
        print(f"Error in video generation pipeline (TextClip or write_videofile): {e}")
        if "ImageMagick" in str(e) or "magick" in str(e).lower() or "convert" in str(e).lower() or "magick.exe" in str(e).lower():
             return "Error generating video: ImageMagick is not installed or not found in your system's PATH. Please install ImageMagick and ensure it's accessible.", 500
        return f"Error generating video: {str(e)}", 500 # Return string representation of e
    finally:
        # Close all moviepy clips
        if audio_clip_for_duration: audio_clip_for_duration.close()
        if audio_clip_for_composition: audio_clip_for_composition.close()
        if txt_clip_resource: txt_clip_resource.close()
        # No separate final_clip_resource to close if txt_clip_resource is the final composite clip

if __name__ == '__main__':
    app.run(debug=True)
