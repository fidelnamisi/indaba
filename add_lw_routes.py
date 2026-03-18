import os

routes = """
# ── LIVING WRITER ──

@app.route('/api/lw/stories', methods=['GET'])
def get_lw_stories():
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    return jsonify({"stories": lw_data.get("stories", [])})

@app.route('/api/lw/stories', methods=['POST'])
def create_lw_story():
    data = request.get_json() or {}
    title = data.get('title')
    if not title or not title.strip():
        return jsonify({"error": "title is required"}), 400
        
    settings = read_json('settings.json') or {}
    lw_max_stories = settings.get('lw_max_stories', 20)
    
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    if len(lw_data.get("stories", [])) >= lw_max_stories:
        return jsonify({"error": "Maximum number of stories in pipeline reached"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    new_story = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "created_at": now,
        "updated_at": now,
        "current_stage": 1,
        "stage_completion": {"1":False,"2":False,"3":False,"4":False,"5":False,"6":False,"7":False},
        "draft_complete": False,
        "draft_complete_at": None,
        "stage1": { "concept_note": "", "devonthink_nudge_shown": False },
        "stage2": { "characters": [], "thematic_values": "", "historical_catastrophe": None, "fragments": [], "world_rules": None, "leviathan_answers": {}, "story_genome": "", "world_of_story_doc": "" },
        "stage3": { "arc_brainstorms": [], "selected_arc_index": None, "four_episode_loglines": [], "tsv_output": "" },
        "stage4": { "treesheets_files": [] },
        "stage5": { "treatment_scenes": [], "descriptionary": [] },
        "stage6": { "narrative_summary": "", "anki_deck_exported": False, "reconstruction_sessions": [] },
        "stage7": { "export_targets": [], "session_notes": "" }
    }
    lw_data["stories"].append(new_story)
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(new_story), 201

@app.route('/api/lw/stories/<story_id>', methods=['GET'])
def get_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>', methods=['PUT'])
def update_lw_story(story_id):
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    data.pop('id', None)
    data.pop('created_at', None)
    
    def deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                deep_update(d[k], v)
            else:
                d[k] = v
                
    deep_update(story, data)
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>', methods=['DELETE'])
def delete_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    stories = lw_data.get("stories", [])
    if not any(s['id'] == story_id for s in stories):
        return jsonify({"error": "Story not found"}), 404
        
    lw_data["stories"] = [s for s in stories if s['id'] != story_id]
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify({"ok": True})

@app.route('/api/lw/stories/<story_id>/advance', methods=['POST'])
def advance_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    stage = story.get('current_stage', 1)
    if stage >= 7:
        return jsonify({"error": "Story is already at the final stage"}), 409
        
    if stage == 2:
        chars = story.get('stage2', {}).get('characters', [])
        if len(chars) < 2:
            return jsonify({"error": "Stage 2 requires at least 2 Character Arc Outlines before advancing"}), 409
    elif stage == 5:
        scenes = story.get('stage5', {}).get('treatment_scenes', [])
        if len(scenes) == 0:
            return jsonify({"error": "Add at least one treatment scene before advancing from Stage 5"}), 409
            
    story['stage_completion'][str(stage)] = True
    story['current_stage'] = stage + 1
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>/complete', methods=['POST'])
def complete_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    if story.get('current_stage', 1) < 7:
        return jsonify({"error": "Story must reach Stage 7 before marking draft complete"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    story['draft_complete'] = True
    story['draft_complete_at'] = now
    story['stage_completion']["7"] = True
    story['updated_at'] = now
    write_json(LIVING_WRITER_FILE, lw_data)
    
    projects = read_json('projects.json') or []
    for p in projects:
        if p.get('name') == story.get('title') and p.get('pipeline') == "Creative Development":
            p['phase'] = "Draft Complete"
            if 'session_notes' in p:
                if p['session_notes']:
                    p['session_notes'] += f"\\n\\nLivingWriter: draft-complete signal received at {now}"
                else:
                    p['session_notes'] = f"LivingWriter: draft-complete signal received at {now}"
            write_json('projects.json', projects)
            print(f"[LivingWriter] Marked project '{p['name']}' as draft-complete")
            break
            
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>/cruxes', methods=['GET'])
def get_lw_story_cruxes(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    try:
        scenes = sorted(scenes, key=lambda x: int(x.get('order', 0)))
    except (TypeError, ValueError):
        pass
        
    res = [{"order": s.get('order', 0), "slug_line": s.get('slug_line', ''), "crux": s.get('crux', '')} for s in scenes]
    return jsonify(res)

@app.route('/api/lw/stories/<story_id>/stage4/open_file', methods=['POST'])
def open_lw_stage4_file(story_id):
    data = request.get_json() or {}
    filepath = data.get('filepath')
    if not filepath or not filepath.strip():
        return jsonify({"error": "filepath is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            subprocess.call(["open", filepath])
        elif sys.platform == "win32":
            os.startfile(filepath)
        else:
            subprocess.call(["xdg-open", filepath])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": "Could not open file. Check that the path is correct and the file exists."}), 500

@app.route('/api/lw/stories/<story_id>/stage2/derive_thematic_values', methods=['POST'])
def derive_thematic_values(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    chars = story.get('stage2', {}).get('characters', [])
    if len(chars) < 2:
        return jsonify({"error": "Add at least 2 characters before deriving thematic values"}), 400
        
    char_lines = []
    for c in chars:
        name = c.get('name', 'Character N')
        crucible = c.get('crucible', '')
        char_lines.append(f"Character: {name}\\nCrucible: {crucible}")
    char_str = "\\n\\n".join(char_lines)
    
    messages = [
        {"role": "system", "content": "You are a story development assistant helping a writer identify the dominant thematic tensions in their story. Return only plain prose, no bullet points, no headers, no markdown. Maximum 300 words."},
        {"role": "user", "content": f"Here are the character crucibles from my story:\\n{char_str}\\nIdentify the 2-3 dominant value tensions that emerge across these characters. For each tension write one paragraph (max 100 words) describing what this world does to people who choose one value over the other. Write in present tense. Be specific and concrete, not abstract."}
    ]
    
    try:
        res_text = call_ai("lw_ai", messages, max_tokens=600)
        return jsonify({"thematic_values": res_text})
    except Exception as e:
        return jsonify({"error": "AI provider unavailable", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage3/arc_brainstorm', methods=['POST'])
def generate_arc_brainstorm(story_id):
    data = request.get_json() or {}
    char_id = data.get('character_id')
    if not char_id:
        return jsonify({"error": "character_id is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    char = next((c for c in story.get('stage2', {}).get('characters', []) if c.get('id') == char_id), None)
    if not char:
        return jsonify({"error": "Character not found"}), 404
        
    genome = story.get('stage2', {}).get('story_genome', '')[:500]
    
    sys_msg = "You are a story structure expert using Lewis Jorstad's Integrated Inner and Outer Journey framework from Mastering Character Arcs. Return only valid JSON, no markdown, no explanation."
    user_msg = f"Character data:\\nOne line: {char.get('character_in_one_line', '')}\\nWound: {char.get('wound', '')}\\nLie: {char.get('lie', '')}\\nCrucible: {char.get('crucible', '')}\\nTerrain: {char.get('terrain', '')}\\nTransformation: {char.get('transformation', '')}\\nWhat they leave behind: {char.get('what_they_leave_behind', '')}\\nStory world context: {genome}\\n\\nGenerate 3 distinct arc possibilities. Return a JSON array of exactly 3 objects. Each object must have these keys: primary_arc_type (Positive, Negative, or Flat), primary_arc_rationale (string), secondary_arc_type (string), secondary_arc_explanation (string), lie (string), truth (string), core_wound (string), arc_summary (string, max 5 sentences of max 15 words each), editorial_recommendation (string)"
    
    try:
        res_text = call_ai("lw_ai", [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], max_tokens=2000)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        if not isinstance(parsed, list):
            raise ValueError("Expected an array")
            
        new_bs = []
        for p in parsed:
            bs = {
                "id": str(uuid.uuid4()),
                "character_id": char_id,
                "primary_arc_type": p.get("primary_arc_type"),
                "primary_arc_rationale": p.get("primary_arc_rationale"),
                "secondary_arc_type": p.get("secondary_arc_type"),
                "secondary_arc_explanation": p.get("secondary_arc_explanation"),
                "lie": p.get("lie"),
                "truth": p.get("truth"),
                "core_wound": p.get("core_wound"),
                "arc_summary": p.get("arc_summary"),
                "editorial_recommendation": p.get("editorial_recommendation")
            }
            new_bs.append(bs)
            story['stage3']['arc_brainstorms'].append(bs)
            
        story['updated_at'] = datetime.utcnow().isoformat() + "Z"
        write_json(LIVING_WRITER_FILE, lw_data)
        return jsonify({"brainstorms": new_bs})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format. Try again.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage3/generate_loglines', methods=['POST'])
def generate_loglines(story_id):
    data = request.get_json() or {}
    bs_id = data.get('brainstorm_id')
    if not bs_id:
        return jsonify({"error": "brainstorm_id is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    bs = next((b for b in story.get('stage3', {}).get('arc_brainstorms', []) if b.get('id') == bs_id), None)
    if not bs:
        return jsonify({"error": "Brainstorm not found"}), 404
        
    sys_msg = "You are a story structure expert. Return only valid JSON, no markdown, no explanation."
    user_msg = f"Arc data:\\nPrimary arc: {bs.get('primary_arc_type')} — {bs.get('primary_arc_rationale')}\\nSecondary arc: {bs.get('secondary_arc_type')}\\nThe lie: {bs.get('lie')}\\nThe truth: {bs.get('truth')}\\nArc summary: {bs.get('arc_summary')}\\n\\nGenerate exactly 4 act-level loglines using Lewis Jorstad's Integrated Inner and Outer Journey framework.\\nRules:\\n- Exactly 25 words each\\n- Present tense, third person\\n- Each logline weaves inner transformation and outer plot conflict simultaneously\\n- Together they trace: Catalyst, Turning Point, Regression, Choice\\n\\nReturn a JSON array of exactly 4 objects. Each object:\\n{{ 'act': 'Act 1' or 'Act 2 Part 1' or 'Act 2 Part 2' or 'Act 3', 'logline': 'exactly 25 words' }}"
    
    try:
        res_text = call_ai("lw_ai", [{"role":"system","content":sys_msg},{"role":"user","content":user_msg}], max_tokens=800)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        if not isinstance(parsed, list) or len(parsed) != 4:
            raise ValueError("Expected an array of length 4")
            
        story['stage3']['four_episode_loglines'] = parsed
        tsv_output = "Act\\tLogline\\n" + "\\n".join([f"{p.get('act')}\\t{p.get('logline')}" for p in parsed])
        story['stage3']['tsv_output'] = tsv_output
        story['updated_at'] = datetime.utcnow().isoformat() + "Z"
        write_json(LIVING_WRITER_FILE, lw_data)
        return jsonify({"loglines": parsed, "tsv_output": tsv_output})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format. Try again.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage2/leviathan_assist', methods=['POST'])
def leviathan_assist(story_id):
    data = request.get_json() or {}
    q_id = data.get('question_id')
    if not q_id:
        return jsonify({"error": "question_id is required"}), 400
        
    q_def = next((q for q in LEVIATHAN_QUESTIONS if q['id'] == q_id), None)
    if not q_def:
        return jsonify({"error": "Invalid question_id"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    curr_answer = story.get('stage2', {}).get('leviathan_answers', {}).get(q_id, "")
    
    genome_context = []
    stage2 = story.get('stage2', {})
    for ref in q_def.get('genome_refs', []):
        if ref == 'characters':
            chars = stage2.get('characters', [])
            cl = [f"{c.get('name')}: {c.get('character_in_one_line')}" for c in chars]
            genome_context.append("Characters:\\n" + "\\n".join(cl))
        else:
            val = stage2.get(ref)
            if val:
                genome_context.append(f"{ref}: {val}")
                
    g_str = "\\n\\n".join(genome_context)
    
    sys_msg = "You are a worldbuilding assistant helping a writer develop their story world. Be specific and concrete. Draw only from the writer's own established material. Maximum 200 words."
    user_msg = f"Question: {q_def['question']}\\nRelevant story material:\\n{g_str}\\nCurrent answer (may be empty): {curr_answer}\\nSuggest a specific, concrete answer to this question that is consistent with the established material. Also flag any contradictions between the current answer and established material. Return JSON:\\n{{ 'suggestion': 'string', 'contradictions': ['string'] }}"
    
    try:
        res_text = call_ai("lw_ai", [{"role":"system","content":sys_msg},{"role":"user","content":user_msg}], max_tokens=400)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        return jsonify({"suggestion": parsed.get("suggestion", ""), "contradictions": parsed.get("contradictions", [])})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage6/export_anki', methods=['POST'])
def export_anki(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    if not scenes:
        return jsonify({"error": "No treatment scenes found. Complete Stage 5 before exporting."}), 400
        
    try:
        import genanki
    except ImportError:
        return jsonify({"error": "genanki is required. Run: pip install genanki"}), 500
        
    h = 0
    for c in story_id:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    
    model_id = h
    deck_id = h ^ 0x12345678
    
    my_model = genanki.Model(
      model_id,
      'LivingWriter Model',
      fields=[
        {'name': 'Front'},
        {'name': 'Back'},
      ],
      templates=[
        {
          'name': 'Card 1',
          'qfmt': '{{Front}}',
          'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
        },
      ])
      
    my_deck = genanki.Deck(deck_id, f"LivingWriter: {story.get('title')}")
    
    for s in scenes:
        front = f"{s.get('slug_line')} — What is the crux of this scene?"
        back = s.get('crux', '')
        my_deck.add_note(genanki.Note(model=my_model, fields=[front, back]))
        
    for d in story.get('stage5', {}).get('descriptionary', []):
        front = f"Describe: {d.get('header', '')}"
        back = d.get('body', '')
        my_deck.add_note(genanki.Note(model=my_model, fields=[front, back]))
        
    filename = f"{story_id}_anki.apkg"
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    genanki.Package(my_deck).write_to_file(filepath)
    
    story['stage6']['anki_deck_exported'] = True
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(LIVING_WRITER_FILE, lw_data)
    
    return jsonify({"download_url": f"/api/lw/exports/{filename}"})

@app.route('/api/lw/exports/<filename>')
def download_lw_export(filename):
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(os.path.join(DATA_DIR, 'exports'), filename)

@app.route('/api/lw/stories/<story_id>/stage7/export', methods=['POST'])
def export_lw_story(story_id):
    data = request.get_json() or {}
    target = data.get('target')
    fmt = data.get('format')
    
    if target not in ["final_draft","scrivener","novelwriter","ulysses","freewrite"]:
        return jsonify({"error": "Invalid export target"}), 400
    if fmt not in ["treatment","cruxes"]:
        return jsonify({"error": "format must be treatment or cruxes"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    try:
        scenes = sorted(scenes, key=lambda x: int(x.get('order', 0)))
    except (TypeError, ValueError):
        pass
        
    if fmt == "cruxes":
        content = "\\n\\n".join([f"{s.get('slug_line', '')}\\n{s.get('crux', '')}" for s in scenes])
        filename = f"{story_id}_cruxes.txt"
    else:
        content = "\\n\\n".join([f"{s.get('slug_line', '')}\\n{s.get('crux', '')}\\n{s.get('scene_description', '')}" for s in scenes])
        filename = f"{story_id}_treatment.txt"
        
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return jsonify({"download_url": f"/api/lw/exports/{filename}"})

@app.route('/api/lw/leviathan/questions')
def get_leviathan_questions():
    return jsonify({"questions": LEVIATHAN_QUESTIONS})

"""

with open('/Users/fidelnamisi/Indaba/app.py', 'r') as f:
    content = f.read()

import re
idx = content.find("if __name__ == '__main__':")
if idx == -1:
    print("Could not find if __name__ block")
else:
    new_content = content[:idx] + routes + content[idx:]
    with open('/Users/fidelnamisi/Indaba/app.py', 'w') as f:
        f.write(new_content)
    print("Appended routes successfully")
