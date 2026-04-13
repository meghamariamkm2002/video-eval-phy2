import gradio as gr
import json
import os

VIDEO_DIR = "Videos"
JSON_DIR = "input"
OUT_DIR = "OUT"
USERS_FILE = "users.json"

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------- GLOBAL ---------------- #

current_user = {"username": None}
is_logged_in = {"value": False}

# ---------------- AUTH ---------------- #

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    return json.load(open(USERS_FILE))

def save_users(users):
    json.dump(users, open(USERS_FILE, "w"))

def signup(username, password):
    users = load_users()
    if username in users:
        return "User already exists"
    users[username] = password
    save_users(users)
    return "Signup successful"

# ---------------- VIDEO ---------------- #

video_files = sorted([
    os.path.join(VIDEO_DIR, f)
    for f in os.listdir(VIDEO_DIR)
    if f.endswith(".mp4")
])

# ---------------- STATE ---------------- #

state = {
    "video_idx": 0,
    "dimension_idx": 0,
    "data": None,
    "video_path": None
}

# ---------------- HELPERS ---------------- #

def load_json(video_path):
    name = os.path.basename(video_path)
    return json.load(open(os.path.join(JSON_DIR, name.replace(".mp4", ".json"))))

def get_out_path(video_path):
    username = current_user["username"]
    name = os.path.basename(video_path)
    path = os.path.join(OUT_DIR, username, name.replace(".mp4", ".json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

# ---------------- LOAD ---------------- #

def load_current():
    if not is_logged_in["value"]:
        return None, "Login first", "", "", {}

    if state["video_idx"] >= len(video_files):
        return None, "🎉 All videos completed!", "", "", {}

    video_path = video_files[state["video_idx"]]
    state["video_path"] = video_path

    data = load_json(video_path)
    state["data"] = data

    dim = data["criteria_set"][state["dimension_idx"]]

    teaching_point = data.get("teaching_point", "")
    prompt = data.get("prompt", "")

    return video_path, dim["dimension"], teaching_point, prompt, dim["criteria"]

# ---------------- SAVE ---------------- #

def save_scores(scores, meta_answer):
    if state["video_path"] is None:
        return

    out_path = get_out_path(state["video_path"])

    if os.path.exists(out_path):
        out_data = json.load(open(out_path))
    else:
        out_data = load_json(state["video_path"])

    dim_idx = state["dimension_idx"]

    # create eval_score if missing
    if "eval_score" not in out_data["criteria_set"][dim_idx]:
        criteria = out_data["criteria_set"][dim_idx]["criteria"]
        out_data["criteria_set"][dim_idx]["eval_score"] = {
            k: {"score": 0, "reason": ""}
            for k in criteria.keys()
        }

    eval_dict = out_data["criteria_set"][dim_idx]["eval_score"]

    # save scores
    for i, key in enumerate(list(eval_dict.keys())):
        if key == "meta":
            continue
        val = scores[i] if i < len(scores) and scores[i] is not None else 0
        eval_dict[key]["score"] = int(val)

    # ✅ UPDATED META OPTIONS
    eval_dict["meta"] = {
        "question_valid": meta_answer if meta_answer else "Maybe"
    }

    json.dump(out_data, open(out_path, "w"), indent=4)
    print(f"✅ Saved → {out_path}")

# ---------------- LOGIN ---------------- #

def login(username, password):
    users = load_users()

    if username in users and users[username] == password:
        current_user["username"] = username
        is_logged_in["value"] = True

        video, dim, teaching, prompt, criteria = load_current()

        updates = []
        for i in range(6):
            if i < len(criteria):
                updates.append(gr.update(label=criteria[str(i+1)], visible=True, value=0))
            else:
                updates.append(gr.update(visible=False))

        return (
            "Login successful",
            gr.update(visible=False),
            gr.update(visible=True),
            video,
            dim,
            teaching,
            prompt,
            *updates,
            gr.update(value="Yes")
        )

    return "Invalid credentials", gr.update(), gr.update(), None, "", "", "", *[gr.update()]*6, gr.update()

# ---------------- NEXT ---------------- #

def next_dimension(*inputs):
    scores = list(inputs[:-1])
    meta_answer = inputs[-1]

    if state["data"] is None:
        return None, "Error", "", "", "Reload app", *[gr.update()]*6, gr.update()

    save_scores(scores, meta_answer)

    if state["dimension_idx"] < len(state["data"]["criteria_set"]) - 1:
        state["dimension_idx"] += 1
    else:
        state["dimension_idx"] = 0
        state["video_idx"] += 1

    video, dim, teaching, prompt, criteria = load_current()

    if video is None:
        return None, dim, teaching, prompt, "🎉 Completed", *[gr.update(visible=False)]*6, gr.update()

    updates = []
    for i in range(6):
        if i < len(criteria):
            updates.append(gr.update(label=criteria[str(i+1)], visible=True, value=0))
        else:
            updates.append(gr.update(visible=False))

    return video, dim, teaching, prompt, "Saved", *updates, gr.update(value="Yes")

# ---------------- UI ---------------- #

with gr.Blocks() as demo:

    gr.Markdown("## 🎥 Video Evaluation Tool")

    # AUTH
    with gr.Column(visible=True) as auth_section:

        with gr.Tab("Login"):
            username = gr.Textbox(label="Username")
            password = gr.Textbox(type="password", label="Password")
            login_btn = gr.Button("Login")
            login_output = gr.Textbox()

        with gr.Tab("Signup"):
            su_user = gr.Textbox(label="Username")
            su_pass = gr.Textbox(type="password", label="Password")
            signup_btn = gr.Button("Signup")
            signup_output = gr.Textbox()

    # EVALUATOR
    with gr.Column(visible=False) as evaluator_section:

        with gr.Row():
            video = gr.Video()

            with gr.Column():
                teaching_box = gr.Textbox(label="📘 Teaching Point", lines=2)
                prompt_box = gr.Textbox(label="🧠 Prompt", lines=3)
                dim_text = gr.Textbox(label="Dimension")

                radios = [
                    gr.Radio([0,1,2], label=f"Criteria {i+1}", value=0)
                    for i in range(6)
                ]

                # ✅ UPDATED META RADIO
                meta_radio = gr.Radio(
                    ["Yes", "No", "Maybe"],
                    label="Are these questions a good way to evaluate this dimension?",
                    value="Yes"
                )

                status = gr.Textbox(label="Status")
                next_btn = gr.Button("Next")

    # EVENTS

    signup_btn.click(signup, [su_user, su_pass], signup_output)

    login_btn.click(
        login,
        inputs=[username, password],
        outputs=[
            login_output,
            auth_section,
            evaluator_section,
            video,
            dim_text,
            teaching_box,
            prompt_box,
            *radios,
            meta_radio
        ]
    )

    next_btn.click(
        next_dimension,
        inputs=[*radios, meta_radio],
        outputs=[
            video,
            dim_text,
            teaching_box,
            prompt_box,
            status,
            *radios,
            meta_radio
        ]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
