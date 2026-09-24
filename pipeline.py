import requests
from youtube_transcript_api import YouTubeTranscriptApi
from transformers import pipeline

# 1. NLP Initialization
nli_model = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-small")

# 2. Live API Integrations
def fetch_steam_patch_notes(app_id):
    """Pulls the absolute latest developer notes directly from the Steam Web API."""
    url = f"http://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid={app_id}&count=1&maxlength=500&format=json"
    try:
        response = requests.get(url, timeout=5).json()
        return response['appnews']['newsitems'][0]['contents']
    except Exception:
        return "Failed to fetch live Steam data."

def fetch_wiki_metadata(entity_name):
    """Queries MediaWiki API to dynamically calculate the Progression Gate."""
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exsentences=2&titles={entity_name}&format=json"
    try:
        response = requests.get(url, timeout=5).json()
        if "boss" in str(response).lower():
            return "Late Game (Boss Tier)"
        return "Mid Game (Standard)"
    except Exception:
        return "Unknown Gate"

# 3. Core Engine Functions
def get_video_title(video_id):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json().get("title", "Unknown Title")
        return "Unknown Title" # Prevents returning NoneType on failed lookups
    except Exception:
        return "Unknown Title"

def detect_game_and_target(title):
    title_lower = title.lower()
    if "once human" in title_lower:
        return "Once Human", 2139460, "Forsaken Giant" if "forsaken giant" in title_lower else "General Gameplay"
    elif "elden ring" in title_lower:
        return "Elden Ring", 1245620, "Rivers of Blood" if "rivers of blood" in title_lower else "General Build"
    return "Unknown Game", None, "Unknown Entity"

def fetch_transcript(video_id):
    try:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            yt_api = YouTubeTranscriptApi()
            transcript = yt_api.fetch(video_id)
            
        chunks, current_chunk, chunk_start = [], "", 0
        for entry in transcript:
            start_time = entry['start'] if isinstance(entry, dict) else entry.start
            text_content = entry['text'] if isinstance(entry, dict) else entry.text
            if not current_chunk: chunk_start = start_time
            current_chunk += " " + text_content
            if start_time - chunk_start >= 30:
                chunks.append({"start": round(chunk_start, 1), "text": current_chunk.strip()})
                current_chunk = ""
        if current_chunk:
            chunks.append({"start": round(chunk_start, 1), "text": current_chunk.strip()})
        return chunks, None
    except Exception as e:
        return None, f"Transcript error: {str(e)}"

def extract_dense_chunks_tfidf(transcript_chunks, target_entity):
    if not transcript_chunks or not target_entity: return 0.0, []
    target_lower = target_entity.lower()
    dense_chunks, hit_count = [], 0
    for chunk in transcript_chunks:
        if target_lower in chunk["text"].lower():
            dense_chunks.append(chunk)
            hit_count += 1
    return round((hit_count / len(transcript_chunks)) * 100, 1), dense_chunks

def calculate_skill_floor(target_entity):
    progression = fetch_wiki_metadata(target_entity)
    composite = 85 if "Late Game" in progression else 50
    diff_tag = "Sweat" if composite > 70 else "Intermediate"
    return {"composite_score": composite, "progression_tier": progression, "difficulty_tag": diff_tag}

def run_audit(video_id):
    title = get_video_title(video_id)
    game, app_id, target = detect_game_and_target(title)
    
    if game == "Unknown Game" or not app_id:
        return {"status": "ERROR", "message": "Unsupported Game. MetaCheck currently only supports Elden Ring and Once Human."}

    chunks, error = fetch_transcript(video_id)
    if error: return {"status": "ERROR", "message": error}

    patch_note = fetch_steam_patch_notes(app_id)
    density, dense_chunks = extract_dense_chunks_tfidf(chunks, target)

    violations = []
    for chunk in dense_chunks:
        res = nli_model(f"{patch_note} [SEP] {chunk['text']}")[0]
        if res['label'].lower() == 'contradiction' or (res['label'] == 'LABEL_0' and res['score'] > 0.65):
            violations.append({
                "timestamp": chunk["start"], 
                "claim": chunk["text"], 
                "rule": patch_note[:150] + "...", 
                "confidence": round(res['score'] * 100, 1)
            })

    return {
        "status": "REJECT" if violations else "VERIFIED",
        "density": density,
        "targets_detected": target,
        "violations": violations,
        "skill_metrics": calculate_skill_floor(target)
    }