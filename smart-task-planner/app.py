from flask import Flask, render_template, request, redirect
import sqlite3
from google import genai


app = Flask(__name__)

client = genai.Client()


# ==========================================
# Database Initialization
# ==========================================

def init_db():

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            title TEXT NOT NULL,

            description TEXT NOT NULL,

            task_date TEXT NOT NULL,

            start_time TEXT NOT NULL,

            end_time TEXT NOT NULL,

            importance TEXT NOT NULL,

            status TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ==========================================
# Conflict Check
# ==========================================

def has_conflict(
    task_date,
    start_time,
    end_time,
    exclude_id=None
):

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    if exclude_id is None:

        cur.execute("""
            SELECT *
            FROM tasks

            WHERE task_date = ?
            AND start_time < ?
            AND end_time > ?
        """, (
            task_date,
            end_time,
            start_time
        ))

    else:

        cur.execute("""
            SELECT *
            FROM tasks

            WHERE task_date = ?
            AND start_time < ?
            AND end_time > ?
            AND id != ?
        """, (
            task_date,
            end_time,
            start_time,
            exclude_id
        ))

    conflict = cur.fetchone()

    conn.close()

    return conflict is not None


# ==========================================
# Get Conflicting Tasks
# ==========================================

def get_conflicting_tasks(
    task_date,
    start_time,
    end_time
):

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM tasks

        WHERE task_date = ?
        AND start_time < ?
        AND end_time > ?

        ORDER BY start_time ASC
    """, (
        task_date,
        end_time,
        start_time
    ))

    conflicts = cur.fetchall()

    conn.close()

    return conflicts


# ==========================================
# Importance
# ==========================================

def importance_value(importance):

    values = {
        "高": 3,
        "中": 2,
        "低": 1
    }

    return values.get(importance, 0)


# ==========================================
# Free Time Calculation
# ==========================================

def get_free_slots(task_date):

    work_start = "09:00"
    work_end = "22:00"

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT start_time, end_time
        FROM tasks

        WHERE task_date = ?

        ORDER BY start_time ASC
    """, (task_date,))

    tasks = cur.fetchall()

    conn.close()

    free_slots = []

    current_time = work_start

    for task in tasks:

        task_start = task[0]
        task_end = task[1]

        if current_time < task_start:

            free_slots.append(
                (
                    current_time,
                    task_start
                )
            )

        if task_end > current_time:

            current_time = task_end

    if current_time < work_end:

        free_slots.append(
            (
                current_time,
                work_end
            )
        )

    return free_slots


# ==========================================
# Convert Time to Minutes
# ==========================================

def time_to_minutes(time_text):

    hour, minute = map(
        int,
        time_text.split(":")
    )

    return hour * 60 + minute


# ==========================================
# Find Fitting Free Slots
# ==========================================

def get_fitting_slots(
    task_date,
    start_time,
    end_time
):

    task_duration = (
        time_to_minutes(end_time)
        - time_to_minutes(start_time)
    )

    free_slots = get_free_slots(task_date)

    fitting_slots = []

    for free_start, free_end in free_slots:

        free_duration = (
            time_to_minutes(free_end)
            - time_to_minutes(free_start)
        )

        if free_duration >= task_duration:

            fitting_slots.append(
                (
                    free_start,
                    free_end
                )
            )

    return fitting_slots


# ==========================================
# Suggested Time Slots
# ==========================================

def get_suggested_slots(
    task_date,
    start_time,
    end_time
):

    task_duration = (
        time_to_minutes(end_time)
        - time_to_minutes(start_time)
    )

    requested_start = time_to_minutes(
        start_time
    )

    fitting_slots = get_fitting_slots(
        task_date,
        start_time,
        end_time
    )

    suggestions = []

    for free_start, free_end in fitting_slots:

        free_start_min = time_to_minutes(
            free_start
        )

        free_end_min = time_to_minutes(
            free_end
        )

        candidate_start = free_start_min

        while (
            candidate_start + task_duration
            <= free_end_min
        ):

            candidate_end = (
                candidate_start
                + task_duration
            )

            start_text = (
                f"{candidate_start // 60:02d}:"
                f"{candidate_start % 60:02d}"
            )

            end_text = (
                f"{candidate_end // 60:02d}:"
                f"{candidate_end % 60:02d}"
            )

            distance = abs(
                candidate_start
                - requested_start
            )

            suggestions.append(
                (
                    distance,
                    start_text,
                    end_text
                )
            )

            # 30 minute intervals
            candidate_start += 30

    # Closest to requested time first
    suggestions.sort(
        key=lambda x: x[0]
    )

    result = []

    for suggestion in suggestions[:3]:

        result.append(
            (
                suggestion[1],
                suggestion[2]
            )
        )

    return result


# ==========================================
# AI Time Recommendation
# ==========================================

def get_ai_time_recommendation(
    title,
    description,
    task_date,
    importance,
    suggestions
):

    if len(suggestions) == 0:

        return "利用できる時間がありません。"

    slot_text = ""

    for start, end in suggestions:

        slot_text += (
            f"{start} ～ {end}\n"
        )

    prompt = f"""
あなたはタスクのスケジュールを支援するAIです。

タスク名: {title}
内容: {description}
予定日: {task_date}
重要度: {importance}

Pythonで確認済みの利用可能時間は以下です。

{slot_text}

ルール:
・必ず上記の時間から1つだけ選ぶ
・新しい時間を作らない
・最もおすすめの時間を1つ選ぶ
・理由を1文で簡潔に説明する
・Markdown記号（**など）は使わない

次の形式で答えてください。

おすすめ: 〇〇 ～ 〇〇
理由: 〇〇
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        print(e)

        return (
            "AIによる時間のおすすめを"
            "取得できませんでした。"
        )


# ==========================================
# Displaced Task Suggestions
# ==========================================

def get_displaced_task_slots(
    task_date,
    task_id,
    old_start,
    old_end,
    reserved_start,
    reserved_end
):

    work_start = "09:00"
    work_end = "22:00"

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    # Get all tasks except the task
    # we are trying to move
    cur.execute("""
        SELECT start_time, end_time
        FROM tasks

        WHERE task_date = ?
        AND id != ?

        ORDER BY start_time ASC
    """, (
        task_date,
        task_id
    ))

    occupied = cur.fetchall()

    conn.close()

    # New high-priority task will use
    # this time, so treat it as occupied
    occupied.append(
        (
            reserved_start,
            reserved_end
        )
    )

    occupied.sort(
        key=lambda x: x[0]
    )

    free_slots = []

    current_time = work_start

    for start, end in occupied:

        if current_time < start:

            free_slots.append(
                (
                    current_time,
                    start
                )
            )

        if end > current_time:

            current_time = end

    if current_time < work_end:

        free_slots.append(
            (
                current_time,
                work_end
            )
        )

    task_duration = (
        time_to_minutes(old_end)
        - time_to_minutes(old_start)
    )

    old_start_minutes = time_to_minutes(
        old_start
    )

    suggestions = []

    for free_start, free_end in free_slots:

        candidate_start = time_to_minutes(
            free_start
        )

        free_end_minutes = time_to_minutes(
            free_end
        )

        while (
            candidate_start + task_duration
            <= free_end_minutes
        ):

            candidate_end = (
                candidate_start
                + task_duration
            )

            start_text = (
                f"{candidate_start // 60:02d}:"
                f"{candidate_start % 60:02d}"
            )

            end_text = (
                f"{candidate_end // 60:02d}:"
                f"{candidate_end % 60:02d}"
            )

            distance = abs(
                candidate_start
                - old_start_minutes
            )

            suggestions.append(
                (
                    distance,
                    start_text,
                    end_text
                )
            )

            candidate_start += 30

    suggestions.sort(
        key=lambda x: x[0]
    )

    result = []

    for suggestion in suggestions[:3]:

        result.append(
            (
                suggestion[1],
                suggestion[2]
            )
        )

    return result


# ==========================================
# Task Input
# ==========================================

@app.route("/", methods=["GET", "POST"])
def form():

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        task_date = request.form["task_date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        importance = request.form["importance"]
        status = request.form["status"]

        # ----------------------------
        # Validation
        # ----------------------------

        if (
            title == ""
            or description == ""
            or task_date == ""
            or start_time == ""
            or end_time == ""
        ):

            return render_template(
                "error.html",
                message=(
                    "必須項目をすべて"
                    "入力してください。"
                )
            )

        if (
            start_time < "09:00"
            or end_time > "22:00"
            or start_time >= end_time
        ):

            return render_template(
                "error.html",
                message=(
                    "時刻を確認してください。"
                    "利用可能時間は"
                    "09:00〜22:00です。"
                )
            )

        # ----------------------------
        # Conflict
        # ----------------------------

        if has_conflict(
            task_date,
            start_time,
            end_time
        ):

            conflicting_tasks = (
                get_conflicting_tasks(
                    task_date,
                    start_time,
                    end_time
                )
            )

            priority_case = "normal"
            conflicting_task = None

            # Priority comparison currently works
            # when exactly one task conflicts
            if len(conflicting_tasks) == 1:

                conflicting_task = (
                    conflicting_tasks[0]
                )

                new_priority = (
                    importance_value(
                        importance
                    )
                )

                existing_priority = (
                    importance_value(
                        conflicting_task[6]
                    )
                )

                if (
                    new_priority
                    > existing_priority
                ):

                    priority_case = (
                        "new_higher"
                    )

                elif (
                    new_priority
                    == existing_priority
                ):

                    priority_case = "same"

                else:

                    priority_case = (
                        "existing_higher"
                    )

            # ----------------------------
            # New task is more important
            # → Move existing task
            # ----------------------------

            if priority_case == "new_higher":

                free_slots = (
                    get_displaced_task_slots(
                        task_date,
                        conflicting_task[0],
                        conflicting_task[4],
                        conflicting_task[5],
                        start_time,
                        end_time
                    )
                )

                ai_time_recommendation = (
                    get_ai_time_recommendation(
                        conflicting_task[1],
                        conflicting_task[2],
                        task_date,
                        conflicting_task[6],
                        free_slots
                    )
                )

            # ----------------------------
            # Existing / Same / Multiple
            # → Find another time
            # for new task
            # ----------------------------

            else:

                free_slots = (
                    get_suggested_slots(
                        task_date,
                        start_time,
                        end_time
                    )
                )

                ai_time_recommendation = (
                    get_ai_time_recommendation(
                        title,
                        description,
                        task_date,
                        importance,
                        free_slots
                    )
                )

            # IMPORTANT:
            # This return is INSIDE
            # has_conflict(), but OUTSIDE
            # the priority if/else.
            return render_template(
                "error.html",
                message=(
                    "この時間は既存のタスクと"
                    "重複しています。"
                ),
                free_slots=free_slots,
                ai_time_recommendation=(
                    ai_time_recommendation
                ),
                priority_case=priority_case,
                conflicting_task=(
                    conflicting_task
                ),
                title=title,
                description=description,
                task_date=task_date,
                start_time=start_time,
                end_time=end_time,
                importance=importance,
                status=status
            )

        # ----------------------------
        # Save to Database
        # Only reached when there is
        # NO conflict
        # ----------------------------

        conn = sqlite3.connect("task.db")
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO tasks
            (
                title,
                description,
                task_date,
                start_time,
                end_time,
                importance,
                status
            )

            VALUES
            (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            task_date,
            start_time,
            end_time,
            importance,
            status
        ))

        conn.commit()
        conn.close()

        return redirect("/list")

    return render_template("form.html")


# ==========================================
# Task List
# ==========================================

@app.route("/list")
def list_page():

    keyword = request.args.get(
        "keyword",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "old"
    )

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    if sort == "id":

        order_by = "id ASC"

    elif sort == "new":

        order_by = (
            "task_date DESC, "
            "start_time DESC"
        )

    elif sort == "title":

        order_by = "title ASC"

    else:

        order_by = (
            "task_date ASC, "
            "start_time ASC"
        )

    if keyword != "":

        cur.execute(f"""
            SELECT *
            FROM tasks

            WHERE title LIKE ?

            ORDER BY {order_by}
        """, (
            "%" + keyword + "%",
        ))

    else:

        cur.execute(f"""
            SELECT *
            FROM tasks

            ORDER BY {order_by}
        """)

    tasks = cur.fetchall()

    conn.close()

    return render_template(
        "list.html",
        tasks=tasks,
        keyword=keyword,
        sort=sort
    )


# ==========================================
# Task Detail
# ==========================================

@app.route("/detail/<int:task_id>")
def detail(task_id):

    keyword = request.args.get(
        "keyword",
        ""
    )

    sort = request.args.get(
        "sort",
        "old"
    )

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM tasks

        WHERE id = ?
    """, (
        task_id,
    ))

    task = cur.fetchone()

    conn.close()

    if task is None:

        return render_template(
            "error.html",
            message="タスクが見つかりません。"
        )

    return render_template(
        "detail.html",
        task=task,
        keyword=keyword,
        sort=sort
    )


# ==========================================
# Task Edit
# ==========================================

@app.route(
    "/edit/<int:task_id>",
    methods=["GET", "POST"]
)
def edit(task_id):

    keyword = request.values.get(
        "keyword",
        ""
    )

    sort = request.values.get(
        "sort",
        "old"
    )

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        task_date = request.form["task_date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        importance = request.form["importance"]
        status = request.form["status"]

        if (
            title == ""
            or description == ""
            or task_date == ""
            or start_time == ""
            or end_time == ""
        ):

            conn.close()

            return render_template(
                "error.html",
                message=(
                    "必須項目をすべて"
                    "入力してください。"
                )
            )

        if (
            start_time < "09:00"
            or end_time > "22:00"
            or start_time >= end_time
        ):

            conn.close()

            return render_template(
                "error.html",
                message=(
                    "時刻を確認してください。"
                    "利用可能時間は"
                    "09:00〜22:00です。"
                )
            )

        if has_conflict(
            task_date,
            start_time,
            end_time,
            task_id
        ):

            conn.close()

            return render_template(
                "error.html",
                message=(
                    "この時間は既存のタスクと"
                    "重複しています。"
                )
            )

        # IMPORTANT:
        # UPDATE only happens if
        # there is NO conflict.

        cur.execute("""
            UPDATE tasks

            SET
                title = ?,
                description = ?,
                task_date = ?,
                start_time = ?,
                end_time = ?,
                importance = ?,
                status = ?

            WHERE id = ?
        """, (
            title,
            description,
            task_date,
            start_time,
            end_time,
            importance,
            status,
            task_id
        ))

        conn.commit()
        conn.close()

        return redirect(
            f"/detail/{task_id}"
            f"?sort={sort}"
            f"&keyword={keyword}"
        )

    # ----------------------------
    # GET Edit Page
    # ----------------------------

    cur.execute("""
        SELECT *
        FROM tasks

        WHERE id = ?
    """, (
        task_id,
    ))

    task = cur.fetchone()

    conn.close()

    if task is None:

        return render_template(
            "error.html",
            message="タスクが見つかりません。"
        )

    return render_template(
        "edit.html",
        task=task,
        keyword=keyword,
        sort=sort
    )


# ==========================================
# Task Delete
# ==========================================

@app.route(
    "/delete/<int:task_id>",
    methods=["POST"]
)
def delete_task(task_id):

    keyword = request.form.get(
        "keyword",
        ""
    )

    sort = request.form.get(
        "sort",
        "old"
    )

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM tasks

        WHERE id = ?
    """, (
        task_id,
    ))

    conn.commit()
    conn.close()

    return redirect(
        f"/list?sort={sort}"
        f"&keyword={keyword}"
    )


# ==========================================
# Free Time Test
# ==========================================

@app.route("/free/<task_date>")
def free_time_test(task_date):

    free_slots = get_free_slots(
        task_date
    )

    result = ""

    for start, end in free_slots:

        result += (
            f"{start} ～ {end}<br>"
        )

    return result


# ==========================================
# AI Recommendation
# ==========================================

@app.route("/recommend")
def recommend():

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT
            title,
            task_date,
            start_time,
            end_time,
            importance

        FROM tasks

        WHERE status = '未着手'

        ORDER BY
            task_date ASC,
            start_time ASC
    """)

    tasks = cur.fetchall()

    conn.close()

    if len(tasks) == 0:

        return render_template(
            "recommend.html",
            recommendation=(
                "現在、未着手のタスクは"
                "ありません。"
            )
        )

    task_text = ""

    for task in tasks:

        task_text += (
            f"タスク名: {task[0]}\n"
            f"予定日: {task[1]}\n"
            f"時間: {task[2]}"
            f" ～ {task[3]}\n"
            f"重要度: {task[4]}\n\n"
        )

    prompt = f"""
あなたはタスク管理を支援するAIです。

以下はユーザーの未着手タスクです。

{task_text}

以下のルールでおすすめの優先順位を考えてください。

・重要度（高・中・低）を考慮する
・予定日時が近いタスクを考慮する
・登録されている予定日時は変更しない
・タスクを勝手に削除・変更しない
・日本語で簡潔に説明する
・おすすめ順に1、2、3のように表示する
・各タスクについて短い理由も説明する
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        recommendation = response.text

    except Exception as e:

        print(e)

        recommendation = (
            "AIおすすめを取得できませんでした。"
            "APIキーや接続を確認してください。"
        )

    return render_template(
        "recommend.html",
        recommendation=recommendation
    )


# ==========================================
# Apply Priority Replacement
# ==========================================

@app.route(
    "/replace_task",
    methods=["POST"]
)
def replace_task():

    existing_task_id = request.form[
        "existing_task_id"
    ]

    moved_start_time = request.form[
        "moved_start_time"
    ]

    moved_end_time = request.form[
        "moved_end_time"
    ]

    title = request.form["title"]
    description = request.form["description"]
    task_date = request.form["task_date"]

    new_start_time = request.form[
        "new_start_time"
    ]

    new_end_time = request.form[
        "new_end_time"
    ]

    importance = request.form[
        "importance"
    ]

    status = request.form[
        "status"
    ]

    conn = sqlite3.connect("task.db")
    cur = conn.cursor()

    # ----------------------------
    # Move existing
    # lower-priority task
    # ----------------------------

    cur.execute("""
        UPDATE tasks

        SET
            start_time = ?,
            end_time = ?

        WHERE id = ?
    """, (
        moved_start_time,
        moved_end_time,
        existing_task_id
    ))

    # ----------------------------
    # Add new higher-priority task
    # at originally requested time
    # ----------------------------

    cur.execute("""
        INSERT INTO tasks
        (
            title,
            description,
            task_date,
            start_time,
            end_time,
            importance,
            status
        )

        VALUES
        (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        description,
        task_date,
        new_start_time,
        new_end_time,
        importance,
        status
    ))

    conn.commit()
    conn.close()

    return redirect("/list")


# ==========================================
# Run Flask
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)