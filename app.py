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

# --- Globální proměnné pro správu AI Follow procesu ---
ai_follow_task_running = False
ai_follow_keyword = None
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
            "keyword": ai_follow_keyword,
            "rate": ai_follow_rate,
            "queue_size": len(ai_follow_queue)
        })

@app.route('/api/ai-follow-start', methods=['POST'])
def ai_follow_start():
    """Spustí AI Follow proces."""
    global ai_follow_task_running, ai_follow_keyword, ai_follow_rate, ai_follow_thread, ai_follow_queue, processed_dids, current_ai_follow_activity
    
    if not is_bluesky_logged_in():
        return jsonify({"status": "error", "message": "Pro spuštění AI Sledování je nutné být přihlášen."})

    data = request.get_json()
    rate = data.get('rate')
    keyword = data.get('keyword')

    if not isinstance(rate, int) or rate <= 0:
        return jsonify({"status": "error", "message": "Prosím zadejte platnou kladnou rychlost."})
    if not keyword or not isinstance(keyword, str):
        return jsonify({"status": "error", "message": "Prosím zadejte klíčové slovo."})

    with ai_follow_lock:
        if ai_follow_task_running:
            return jsonify({"status": "info", "message": "AI Sledování již běží."})

        ai_follow_task_running = True
        ai_follow_keyword = keyword
        ai_follow_rate = rate
        ai_follow_queue.clear() # Vyprázdníme frontu pro nový start
        processed_dids.clear() # Resetujeme sledované DID (pro účely nové "run")
        current_ai_follow_activity = f"Spuštěno s klíčovým slovem '{keyword}' a rychlostí {rate} lidí/hod."
        
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

    return jsonify({"status": "success", "message": "AI Sledování bylo spuštěno!"})

@app.route('/api/ai-follow-stop', methods=['POST'])
def ai_follow_stop():
    """Zastaví AI Follow proces."""
    global ai_follow_task_running, ai_follow_thread, current_ai_follow_activity
    with ai_follow_lock:
        if not ai_follow_task_running:
            return jsonify({"status": "info", "message": "AI Sledování již neběží."})

        ai_follow_task_running = False
        # Počkáme na dokončení vlákna (s timeoutem)
        if ai_follow_thread and ai_follow_thread.is_alive():
            ai_follow_thread.join(timeout=5)
            if ai_follow_thread.is_alive():
                print("Upozornění: AI Follow vlákno se nepodařilo ukončit včas.")
        ai_follow_thread = None # Resetujeme referenci na vlákno
        current_ai_follow_activity = "Zastaveno" # Aktualizovat aktivitu

    return jsonify({"status": "success", "message": "AI Sledování bylo zastaveno."})

@app.route('/api/ai-follow-activity', methods=['GET'])
def ai_follow_activity():
    """Vrací aktuální zprávu o aktivitě AI Follow."""
    with ai_follow_lock:
        return jsonify({
            "status": "success",
            "message": current_ai_follow_activity
        })


def _run_ai_follow_task():
    """
    Pozadí úloha pro AI Sledování.
    Tato funkce běží v samostatném vlákně a řídí proces vyhledávání a sledování.
    Vyhledává uživatele podle klíčového slova a poté sleduje jejich followers.
    """
    global ai_follow_task_running, ai_follow_keyword, ai_follow_rate, ai_follow_queue, last_follow_time, processed_dids, current_ai_follow_activity
    
    print(f"AI Follow Thread: Spuštěno s klíčovým slovem '{ai_follow_keyword}' a rychlostí {ai_follow_rate} lidí/hod.")

    # Čas mezi jednotlivými follow operacemi (v sekundách)
    seconds_per_follow = 3600 / ai_follow_rate if ai_follow_rate > 0 else 0
    
    # Rozsah náhodné variace (např. +/- 20%)
    random_variation_percent = 0.2 

    # Abychom nepřetížili API Bluesky, nastavíme minimální zpoždění pro vyhledávání nových uživatelů
    search_user_delay = 60 # Hledáme nového uživatele pro získání followers každých 60 sekund (nebo když je fronta prázdná)
    last_search_user_time = 0
    
    # Uložíme si DID uživatelů, jejichž followery jsme již prohledali, abychom se neopakovali
    searched_user_dids = set()

    while True:
        with ai_follow_lock:
            if not ai_follow_task_running:
                print("AI Follow Thread: Zastavování úlohy.")
                current_ai_follow_activity = "Zastaveno"
                break 

        current_time = time.time()

        # Krok 1: Pokus o následování uživatele z fronty
        if ai_follow_queue:
            # Vypočítáme randomizované zpoždění pro tento konkrétní follow
            delay_factor = 1 + random.uniform(-random_variation_percent, random_variation_percent)
            current_follow_delay = seconds_per_follow * delay_factor

            if current_time - last_follow_time >= current_follow_delay:
                with ai_follow_lock:
                    if not ai_follow_queue: # Zkontrolovat znovu, pokud se mezitím fronta vyprázdnila
                        continue
                    target_did = ai_follow_queue.popleft() 
                
                # Zkontrolovat, zda již tento DID nesledujeme nebo jsme ho nedávno zpracovali
                if target_did in processed_dids:
                    print(f"AI Follow Thread: DID {target_did} již zpracován/sledován, přeskočeno. (zbývá ve frontě: {len(ai_follow_queue)})")
                    with ai_follow_lock:
                        current_ai_follow_activity = f"Přeskakuji již zpracovaného DID. Fronta: {len(ai_follow_queue)}"
                    continue 
                
                with ai_follow_lock:
                    current_ai_follow_activity = f"Sleduji uživatele: {target_did} (zbývá: {len(ai_follow_queue)})"
                print(f"AI Follow Thread: Pokus o následování DID: {target_did} (zbývá ve frontě: {len(ai_follow_queue)})")
                
                try:
                    bluesky_client.follow(target_did)
                    print(f"AI Follow Thread: Úspěšně následován DID: {target_did}")
                    with ai_follow_lock:
                        processed_dids.add(target_did)
                        current_ai_follow_activity = f"Úspěšně následován: {target_did} (fronta: {len(ai_follow_queue)})"
                    last_follow_time = time.time()
                except Exception as e:
                    print(f"AI Follow Thread: Chyba při následování DID {target_did}: {e}")
                    with ai_follow_lock:
                        processed_dids.add(target_did) # Označit jako zpracované, aby se ho znovu nepokoušel následovat
                        current_ai_follow_activity = f"Chyba při následování: {target_did} ({e}). Fronta: {len(ai_follow_queue)}"
                
            else:
                time_to_wait = current_follow_delay - (current_time - last_follow_time)
                # print(f"AI Follow Thread: Čekám na další follow: {time_to_wait:.2f}s")
                time.sleep(time_to_wait + 0.1) 
                continue 
        
        # Krok 2: Pokud je fronta prázdná NEBO je čas na nové vyhledávání vhodných uživatelů
        if (not ai_follow_queue) or (current_time - last_search_user_time >= search_user_delay):
            with ai_follow_lock:
                current_ai_follow_activity = f"Hledám nové uživatele s klíčovým slovem '{ai_follow_keyword}'..."
            print(f"AI Follow Thread: Fronta prázdná nebo čas na hledání nového vhodného uživatele pro followery. Hledám '{ai_follow_keyword}'...")
            
            try:
                search_actors_response = bluesky_client.search_actors(q=ai_follow_keyword, limit=20) 
                
                if search_actors_response and search_actors_response.actors:
                    suitable_user_did = None
                    for actor in search_actors_response.actors:
                        if actor.did not in searched_user_dids:
                            suitable_user_did = actor.did
                            with ai_follow_lock:
                                searched_user_dids.add(actor.did) 
                            break

                    if suitable_user_did:
                        print(f"AI Follow Thread: Nalezen vhodný uživatel pro prohledání followerů: {suitable_user_did}")
                        with ai_follow_lock:
                            current_ai_follow_activity = f"Získávám sledující uživatele: {suitable_user_did}..."
                        
                        followers_of_suitable_user = []
                        followers_cursor = None
                        while True:
                            try:
                                resp = bluesky_client.get_followers(actor=suitable_user_did, limit=100, cursor=followers_cursor)
                                if resp and resp.followers:
                                    for follower_item in resp.followers:
                                        if follower_item.did not in processed_dids:
                                            with ai_follow_lock:
                                                ai_follow_queue.append(follower_item.did)
                                                processed_dids.add(follower_item.did) 
                                    followers_cursor = resp.cursor
                                else:
                                    break
                                if not followers_cursor:
                                    break
                            except Exception as e_inner:
                                print(f"AI Follow Thread: Chyba při načítání sledujících pro {suitable_user_did}: {e_inner}")
                                with ai_follow_lock:
                                    current_ai_follow_activity = f"Chyba při získávání sledujících pro {suitable_user_did}: {e_inner}"
                                break 

                        print(f"AI Follow Thread: Přidáno {len(ai_follow_queue)} nových uživatelů do fronty z followerů {suitable_user_did}. Celková fronta: {len(ai_follow_queue)}")
                        with ai_follow_lock:
                            current_ai_follow_activity = f"Fronta doplněna. Nová fronta: {len(ai_follow_queue)}"
                    else:
                        print(f"AI Follow Thread: Nenašel se žádný nový vhodný uživatel podle klíčového slova '{ai_follow_keyword}'.")
                        with ai_follow_lock:
                            current_ai_follow_activity = f"Žádný nový vhodný uživatel s klíčovým slovem '{ai_follow_keyword}' nenalezen."
                else:
                    print(f"AI Follow Thread: Žádné profily s klíčovým slovem '{ai_follow_keyword}' nenalezeny.")
                    with ai_follow_lock:
                        current_ai_follow_activity = f"Žádné profily s klíčovým slovem '{ai_follow_keyword}' nenalezeny."
            
            except Exception as e:
                print(f"AI Follow Thread: Chyba při vyhledávání vhodných uživatelů: {e}")
                with ai_follow_lock:
                    current_ai_follow_activity = f"Chyba při vyhledávání vhodných uživatelů: {e}"
            
            last_search_user_time = time.time()
        
        # Pokud je fronta stále prázdná a nemáme co sledovat, spíme delší dobu
        if not ai_follow_queue:
            time.sleep(10) # Spíme 10 sekund, než zkusíme znovu hledat nebo pokračovat
        else:
            time.sleep(1) # Krátká pauza, pokud fronta není prázdná, aby se nezasekla smyčka
