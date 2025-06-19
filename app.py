import time
import threading
from collections import deque
import random # Importujeme pro randomizaci zpoždění
from flask import Flask, render_template, request, jsonify, session
import os
from atproto import Client, models

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_please_change_this!')

bluesky_client = Client()

# --- Debugging: Kontrola atributů klienta po inicializaci ---
print(f"DEBUG: Typ bluesky_client po inicializaci: {type(bluesky_client)}")
print(f"DEBUG: Atributy bluesky_client po inicializaci: {dir(bluesky_client)}")
# --- Konec debuggingu ---

# --- Globální proměnné pro správu AI Follow procesu ---
ai_follow_task_running = False
ai_follow_keyword_for_display = None # Pouze pro zobrazení v UI, ne pro logiku vyhledávání
ai_follow_rate = None # lidé za hodinu
ai_follow_thread = None
ai_follow_queue = deque() # Fronta DID uživatelů k následování
last_follow_time = 0 # Čas posledního follow, pro řízení rychlosti

# Zde budeme sledovat již navštívené DID, abychom se vyhnuli opakovanému zpracování
# a také uživatele, které již sledujeme, nebo které jsme se pokusili sledovat.
processed_dids = set() # DIDs, které jsme již zpracovali (follow/přeskočili)
current_ai_follow_activity = "Nespustěno" # Zpráva pro frontend o aktuální aktivitě

ai_follow_lock = threading.Lock()
# --- Konec globálních proměnných ---

def is_bluesky_logged_in():
    return bluesky_client.me is not None

def get_bluesky_handle():
    return bluesky_client.me.handle if is_bluesky_logged_in() else None


@app.route('/')
def index():
    return render_template('index.html', is_logged_in=is_bluesky_logged_in(), user_handle=get_bluesky_handle())

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/bluesky-login', methods=['POST'])
def bluesky_login():
    data = request.get_json()
    handle = data.get('handle')
    password = data.get('password')

    handle = handle.strip() if handle else None
    password = password.strip() if password else None
    
    print(f"Přihlašovací pokus: Handle '{handle}', Délka hesla: {len(password) if password else 0}")

    if not handle or not password:
        return jsonify({"status": "error", "message": "Prosím, zadejte Bluesky handle a heslo."})

    try:
        bluesky_client.login(handle, password)
        if is_bluesky_logged_in():
            return jsonify({"status": "success", "message": f"Úspěšně přihlášen jako {get_bluesky_handle()}!", "handle": get_bluesky_handle()})
        else:
            return jsonify({"status": "error", "message": "Přihlášení se nezdařilo. Zkontrolujte prosím své údaje."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při přihlašování: {str(e)}"})

@app.route('/api/bluesky-logout', methods=['POST'])
def bluesky_logout():
    global ai_follow_task_running, ai_follow_thread, current_ai_follow_activity
    with ai_follow_lock:
        if ai_follow_task_running:
            ai_follow_task_running = False
            if ai_follow_thread and ai_follow_thread.is_alive():
                ai_follow_thread.join(timeout=5)
            current_ai_follow_activity = "Nespustěno (odhlášeno)" # Aktualizovat aktivitu
    try:
        bluesky_client.logout()
        return jsonify({"status": "success", "message": "Odhlášeno z Bluesky."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při odhlašování: {str(e)}"})


@app.route('/api/get-stats', methods=['GET'])
def get_stats():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Nelze načíst statistiky. Nejste přihlášeni."})
    
    followers_count = "N/A"
    follows_count = "N/A"

    try:
        followers_list = []
        cursor = None
        while True:
            response = bluesky_client.get_followers(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.followers:
                followers_list.extend(response.followers)
                cursor = response.cursor
            else:
                break
            if not cursor:
                break
        followers_count = len(followers_list)
    except Exception as e:
        print(f"Chyba při načítání počtu sledujících: {e}")
        followers_count = "Chyba"

    try:
        follows_list = []
        cursor = None
        while True:
            response = bluesky_client.get_follows(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.follows:
                follows_list.extend(response.follows)
                cursor = response.cursor
            else:
                break
            if not cursor:
                break
        follows_count = len(follows_list)
    except Exception as e:
        print(f"Chyba při načítání počtu sledovaných: {e}")
        follows_count = "Chyba"

    stats = {
        'followers': followers_count,
        'following': follows_count
    }
    return jsonify({"status": "success", "stats": stats})

@app.route('/api/ai-post', methods=['POST'])
def ai_post():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Post je nutné být přihlášen."})
    data = request.get_json()
    post_content = data.get('content')

    if not post_content:
        post_content = "Automaticky generovaný příspěvek od Bluesky AI Manager."

    try:
        post_ref = bluesky_client.post(post_content)
        return jsonify({"status": "success", "message": f"Příspěvek úspěšně vytvořen! URI: {post_ref.uri}"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vytváření příspěvků: {str(e)}"})

@app.route('/api/ai-like', methods=['POST'])
def ai_like():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Like je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri')

    if not post_uri:
        return jsonify({"status": "error", "message": "Pro lajknutí je vyžadováno URI příspěvku."})

    try:
        rkey = post_uri.rsplit('/', 1)[-1]
        bluesky_client.like(post_uri, rkey)
        return jsonify({"status": "success", "message": f"Příspěvek {post_uri} úspěšně lajknut!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při lajkování příspěvků: {str(e)}"})

@app.route('/api/ai-comment', methods=['POST'])
def ai_comment():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Comment je nutné být přihlášen."})
    data = request.get_json()
    post_uri = data.get('uri')
    comment_text = data.get('comment')

    if not post_uri or not comment_text:
        return jsonify({"status": "error", "message": "Pro komentář je vyžadováno URI a text komentáře."})

    try:
        thread_response = bluesky_client.get_post_thread(post_uri)
        
        if not (thread_response and thread_response.thread and hasattr(thread_response.thread, 'post')):
            return jsonify({"status": "error", "message": f"Příspěvek s URI {post_uri} nebyl nalezen nebo je neplatný."})

        target_post = thread_response.thread.post
        
        root_ref = models.create_strong_ref(target_post.uri, target_post.cid)
        parent_ref = models.create_strong_ref(target_post.uri, target_post.cid)

        bluesky_client.post(text=comment_text, reply_to=models.ReplyRef(root=root_ref, parent=parent_ref))
        
        return jsonify({"status": "success", "message": f"Komentář k {post_uri} úspěšně přidán!"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vytváření komentáře: {str(e)}"})

@app.route('/api/ai-follow', methods=['POST'])
def ai_follow():
    # Tato funkce by již neměla být volána přímo, nahrazena logikou v _run_ai_follow_task
    return jsonify({"status": "error", "message": "Tato funkce je nyní řízena AI Sledováním."})

@app.route('/api/ai-unfollow', methods=['POST'])
def ai_unfollow():
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro AI Unfollow je nutné být přihlášen."})
    data = request.get_json()
    target_handle = data.get('handle')

    if not target_handle:
        return jsonify({"status": "error", "message": "Pro zrušení sledování je vyžadován handle uživatele."})

    try:
        profile = bluesky_client.get_profile(target_handle)
        if not (profile and profile.did):
            return jsonify({"status": "error", "message": f"Uživatel {target_handle} nenalezen."})
        
        target_did = profile.did

        found_follow_uri = None
        found_follow_cid = None
        
        cursor = None
        while True:
            response = bluesky_client.get_follows(actor=bluesky_client.me.did, limit=100, cursor=cursor)
            if response and response.follows:
                for follow_item in response.follows:
                    if follow_item.did == target_did:
                        found_follow_uri = follow_item.uri
                        found_follow_cid = follow_item.cid
                        break
                if found_follow_uri:
                    break
                cursor = response.cursor
            else:
                break
            if not cursor:
                break

        if found_follow_uri and found_follow_cid:
            bluesky_client.delete_record(found_follow_uri, found_follow_cid)
            return jsonify({"status": "success", "message": f"Uživatel {target_handle} úspěšně přestal být sledován!"})
        else:
            return jsonify({"status": "error", "message": f"Uživatel {target_handle} nebyl nalezen mezi sledovanými účty nebo záznam o sledování je neplatný."})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při zrušení sledování: {str(e)}"})


# --- Nové API endpointy pro AI Follow funkci ---
@app.route('/api/ai-follow-status', methods=['GET'])
def ai_follow_status():
    """Vrací aktuální stav AI Follow procesu."""
    with ai_follow_lock:
        return jsonify({
            "status": "success",
            "running": ai_follow_task_running,
            "keyword": ai_follow_keyword_for_display, # Používáme novou proměnnou
            "rate": ai_follow_rate,
            "queue_size": len(ai_follow_queue)
        })

@app.route('/api/ai-follow-start', methods=['POST'])
def start_follow_processing(): # Přejmenováno pro jasnost
    """Spustí proces zpracování fronty AI Follow."""
    global ai_follow_task_running, ai_follow_rate, ai_follow_thread, processed_dids, current_ai_follow_activity, ai_follow_keyword_for_display
    
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro spuštění zpracování je nutné být přihlášen."})

    data = request.get_json()
    rate = data.get('rate')
    keyword = data.get('keyword') # Získáme klíčové slovo jen pro zobrazení

    if not isinstance(rate, int) or rate <= 0:
        return jsonify({"status": "error", "message": "Prosím zadejte platnou kladnou rychlost pro zpracování fronty."})

    with ai_follow_lock:
        if ai_follow_task_running:
            return jsonify({"status": "info", "message": "Zpracování AI Sledování již běží."})

        ai_follow_task_running = True
        ai_follow_rate = rate
        ai_follow_keyword_for_display = keyword # Uložíme pro zobrazení
        current_ai_follow_activity = f"Spuštěno zpracování fronty s rychlostí {rate} lidí/hod."
        
        # Získáme DID aktuálně sledovaných uživatelů, abychom je nepřidávali do processed_dids
        # a vyhnuli se pokusu o followání již sledovaných.
        try:
            my_follows_response = bluesky_client.get_follows(actor=bluesky_client.me.did)
            for f in my_follows_response.follows:
                processed_dids.add(f.did)
            print(f"AI Follow Thread: Přednačteno {len(processed_dids)} již sledovaných uživatelů.")
        except Exception as e:
            print(f"AI Follow Thread: Chyba při přednačítání sledovaných uživatelů: {e}")
            current_ai_follow_activity = f"Chyba při přednačítání sledovaných uživatelů: {e}"

        # Spustíme vlákno pro pozadí úlohu
        ai_follow_thread = threading.Thread(target=_run_ai_follow_task)
        ai_follow_thread.daemon = True # Povolí ukončení vlákna s hlavní aplikací
        ai_follow_thread.start()

    return jsonify({"status": "success", "message": "Zpracování fronty AI Sledování bylo spuštěno!"})

@app.route('/api/ai-follow-stop', methods=['POST'])
def stop_follow_processing(): # Přejmenováno pro jasnost
    """Zastaví proces zpracování fronty AI Follow."""
    global ai_follow_task_running, ai_follow_thread, current_ai_follow_activity
    with ai_follow_lock:
        if not ai_follow_task_running:
            return jsonify({"status": "info", "message": "Zpracování AI Sledování již neběží."})

        ai_follow_task_running = False
        if ai_follow_thread and ai_follow_thread.is_alive():
            ai_follow_thread.join(timeout=5)
            if ai_follow_thread.is_alive():
                print("Upozornění: AI Follow vlákno se nepodařilo ukončit včas.")
        ai_follow_thread = None
        current_ai_follow_activity = "Zastaveno" # Aktualizovat aktivitu

    return jsonify({"status": "success", "message": "Zpracování fronty AI Sledování bylo zastaveno."})

@app.route('/api/ai-follow-activity', methods=['GET'])
def ai_follow_activity():
    """Vrací aktuální zprávu o aktivitě AI Follow."""
    with ai_follow_lock:
        return jsonify({
            "status": "success",
            "message": current_ai_follow_activity
        })

@app.route('/api/search-follow-sources', methods=['GET'])
def search_follow_sources():
    """
    Vyhledá uživatele podle klíčového slova a vrátí je seřazené podle počtu sledujících.
    """
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro vyhledávání zdrojových uživatelů je nutné být přihlášen."})

    keyword = request.args.get('keyword', '')
    if not keyword:
        return jsonify({"status": "error", "message": "Je potřeba zadat klíčové slovo pro vyhledávání."})

    try:
        # Volání search_actors se nyní nachází přímo pod bluesky_client.bsky.actor
        search_results = bluesky_client.bsky.actor.search_actors(q=keyword, limit=25)
        
        potential_users = []
        if search_results and search_results.actors:
            for actor in search_results.actors:
                try:
                    profile_details = bluesky_client.get_profile(actor.did)
                    if profile_details:
                        potential_users.append({
                            "did": actor.did,
                            "handle": actor.handle,
                            "followers_count": profile_details.followersCount
                        })
                except Exception as e:
                    print(f"Chyba při získávání profilu pro {actor.handle}: {e}")
                    continue
        
        potential_users_sorted = sorted(
            potential_users, 
            key=lambda x: x['followers_count'] if isinstance(x['followers_count'], int) else -1,
            reverse=True
        )
        
        return jsonify({
            "status": "success",
            "users": potential_users_sorted[:50]
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při vyhledávání zdrojových uživatelů: {str(e)}"})

@app.route('/api/add-followers-to-queue', methods=['POST'])
def add_followers_to_queue():
    """
    Načte sledující daného uživatele a přidá je do globální fronty AI Follow.
    """
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro přidání sledujících do fronty je nutné být přihlášen."})

    data = request.get_json()
    target_user_did = data.get('target_user_did')

    if not target_user_did:
        return jsonify({"status": "error", "message": "Nebylo zadáno DID cílového uživatele."})

    followers_added_count = 0
    total_followers_found = 0
    try:
        followers_list = []
        cursor = None
        while True:
            response = bluesky_client.get_followers(actor=target_user_did, limit=100, cursor=cursor)
            if response and response.followers:
                followers_list.extend(response.followers)
                cursor = response.cursor
                total_followers_found += len(response.followers)
            else:
                break
            if not cursor:
                break
        
        with ai_follow_lock:
            for follower_item in followers_list:
                if follower_item.did != bluesky_client.me.did and follower_item.did not in processed_dids: 
                    ai_follow_queue.append(follower_item.did)
                    processed_dids.add(follower_item.did) 
                    followers_added_count += 1
            
            current_ai_follow_activity = f"Přidáno {followers_added_count} sledujících z {target_user_did}. Celkem ve frontě: {len(ai_follow_queue)}"

        return jsonify({
            "status": "success",
            "message": f"Nalezeno {total_followers_found} sledujících uživatele {target_user_did}, přidáno {followers_added_count} nových do fronty. Celkem ve frontě: {len(ai_follow_queue)}."
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"Chyba při přidávání sledujících do fronty od {target_user_did}: {str(e)}"})


def _run_ai_follow_task():
    """
    Pozadí úloha pro AI Sledování.
    Tato funkce běží v samostatném vlákně a řídí proces sledování uživatelů z fronty.
    """
    global ai_follow_task_running, ai_follow_rate, ai_follow_queue, last_follow_time, processed_dids, current_ai_follow_activity
    
    print(f"AI Follow Thread: Spuštěno zpracování fronty s rychlostí {ai_follow_rate} lidí/hod.")
    current_ai_follow_activity = f"Zpracovávám frontu. Rychlost: {ai_follow_rate} lidí/hod. Fronta: {len(ai_follow_queue)}"

    seconds_per_follow = 3600 / ai_follow_rate if ai_follow_rate > 0 else 0
    random_variation_percent = 0.2 

    while True:
        with ai_follow_lock:
            if not ai_follow_task_running:
                print("AI Follow Thread: Zastavování úlohy.")
                current_ai_follow_activity = "Zastaveno"
                break 

        current_time = time.time()

        if ai_follow_queue:
            delay_factor = 1 + random.uniform(-random_variation_percent, random_variation_percent)
            current_follow_delay = seconds_per_follow * delay_factor

            if current_time - last_follow_time >= current_follow_delay:
                with ai_follow_lock:
                    if not ai_follow_queue: # Zkontrolovat znovu, pokud se mezitím fronta vyprázdnila
                        continue
                    target_did = ai_follow_queue.popleft() 
                
                if target_did in processed_dids:
                    print(f"AI Follow Thread: DID {target_did} již zpracován/sledován, přeskočeno. (zbývá ve frontě: {len(ai_follow_queue)})")
                    with ai_follow_lock:
                        current_ai_follow_activity = f"Přeskakuji již zpracovaného DID. Fronta: {len(ai_follow_queue)}"
                    continue 
                
                with ai_follow_lock:
                    target_handle_for_log = target_did 
                    try:
                        profile_temp = bluesky_client.get_profile(target_did)
                        if profile_temp and profile_temp.handle:
                            target_handle_for_log = profile_temp.handle
                    except Exception as e_get_profile:
                        print(f"Nelze získat handle pro {target_did}: {e_get_profile}")
                    current_ai_follow_activity = f"Sleduji uživatele: @{target_handle_for_log} (zbývá ve frontě: {len(ai_follow_queue)})"
                
                print(f"AI Follow Thread: Pokus o následování DID: {target_did} (zbývá ve frontě: {len(ai_follow_queue)})")
                
                try:
                    bluesky_client.follow(target_did)
                    print(f"AI Follow Thread: Úspěšně následován DID: {target_did}")
                    with ai_follow_lock:
                        processed_dids.add(target_did)
                        current_ai_follow_activity = f"Úspěšně následován: @{target_handle_for_log} (fronta: {len(ai_follow_queue)})"
                    last_follow_time = time.time()
                except Exception as e:
                    print(f"AI Follow Thread: Chyba při následování DID {target_did}: {e}")
                    with ai_follow_lock:
                        processed_dids.add(target_did) # Označit jako zpracované, aby se ho znovu nepokoušel následovat
                        current_ai_follow_activity = f"Chyba při následování: @{target_handle_for_log} ({e}). Fronta: {len(ai_follow_queue)}"
                
            else:
                time_to_wait = current_follow_delay - (current_time - last_follow_time)
                time.sleep(time_to_wait + 0.1) 
                continue 
        else: # Fronta je prázdná
            with ai_follow_lock:
                current_ai_follow_activity = "Fronta pro sledování je prázdná. Čekám na nové uživatele..."
            print("AI Follow Thread: Fronta prázdná, čekám na nové uživatele.")
            time.sleep(5) # Spíme kratší dobu, pokud je fronta prázdná, aby se rychleji reagovalo na nové položky
