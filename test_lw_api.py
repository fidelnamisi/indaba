import requests
import json
import time
import subprocess
import os

def check():
    url = "http://localhost:5050"
    
    # Create story
    print("Testing create story...")
    resp = requests.post(f"{url}/api/lw/stories", json={"title": "Test Story"})
    if resp.status_code != 201:
        print(f"Failed! Expected 201, got {resp.status_code}")
        print(resp.text)
        return False
    data = resp.json()
    story_id = data.get("id")
    print(f"Created story id: {story_id}")
    
    # Get story
    print("Testing get story...")
    resp = requests.get(f"{url}/api/lw/stories/{story_id}")
    if resp.status_code != 200:
        print("Failed get story")
        return False
        
    # Advance stage
    print("Testing advance stage...")
    resp = requests.post(f"{url}/api/lw/stories/{story_id}/advance")
    if resp.status_code != 200 or resp.json().get('current_stage') != 2:
        print(f"Failed advance stage! Expected 200 and stage 2, got {resp.status_code}")
        print(resp.text)
        return False
        
    # Advance stage 2 fail
    print("Testing advance stage 2 failure...")
    resp = requests.post(f"{url}/api/lw/stories/{story_id}/advance")
    if resp.status_code != 409:
        print(f"Failed expected 409, got {resp.status_code}")
        return False
        
    # Get cruxes
    print("Testing get cruxes...")
    resp = requests.get(f"{url}/api/lw/stories/{story_id}/cruxes")
    if resp.status_code != 200 or resp.json() != []:
        print("Failed get cruxes")
        return False
        
    # Get Leviathan questions
    print("Testing leviathan questions...")
    resp = requests.get(f"{url}/api/lw/leviathan/questions")
    if resp.status_code != 200 or len(resp.json().get('questions', [])) != 52:
        print("Failed leviathan questions")
        return False
        
    # Get hub summary
    print("Testing hub summary...")
    resp = requests.get(f"{url}/api/hub/summary")
    if resp.status_code != 200:
        print("Failed hub summary")
        return False
    sm = resp.json().get('living_writer', {})
    if sm.get('stories_in_pipeline') != 1 or sm.get('furthest_stage') != 2:
        print(f"Failed hub summary asserts: {sm}")
        return False
        
    # Delete story
    print("Testing delete story...")
    resp = requests.delete(f"{url}/api/lw/stories/{story_id}")
    if resp.status_code != 200:
        print("Failed delete story")
        return False
        
    print("ALL TESTS PASSED")
    return True

if __name__ == "__main__":
    check()
