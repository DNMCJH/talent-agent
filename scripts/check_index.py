"""Quick check of indexed data."""
from qdrant_client import QdrantClient

client = QdrantClient(path="./data/qdrant_storage")
info = client.get_collection("projects")
print(f"Collection: {info.points_count} points, dim={info.config.params.vectors.size}")

results = client.scroll(collection_name="projects", limit=10)
for p in results[0]:
    name = p.payload["name"]
    stack = p.payload["stack"][:5]
    topics = p.payload["topics"][:4]
    print(f"  {name}")
    print(f"    stack: {stack}")
    print(f"    topics: {topics}")
    print()

client.close()
