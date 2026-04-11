from youtube_transcript_api import YouTubeTranscriptApi
api = YouTubeTranscriptApi()
data = api.fetch("xQR5-Nk9N6o", languages=["ko", "en"])
print(f"Type: {type(data).__name__}")
print(f"Has len: {hasattr(data, '__len__')}")
items = list(data)
print(f"Count: {len(items)}")
print(f"First: {items[0] if items else None}")
