# common/audio_convert.py

from pydub import AudioSegment
import os

def any_to_wav(input_path, output_path):
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="wav")
        return True
    except Exception as e:
        print(f"音訊轉換失敗: {str(e)}")
        return False
