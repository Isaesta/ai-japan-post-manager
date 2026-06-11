import json
import os
import pandas as pd
import psycopg
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from urllib.parse import quote
from PIL import Image
from pathlib import Path

st.set_page_config(
    page_title="AIと日本人 投稿管理ツール",
    layout="wide"
)

load_dotenv()

# GPTsのURLを取得
GPT_LINKS = {
    "善意あるAI社会シリーズ：": [
        ("🎬 シナリオライター", os.getenv("GPT_SCENARIO_WRITER")),
        ("📝 エディター", os.getenv("GPT_EDITOR")),
        ("🎨 クリエイター", os.getenv("GPT_CREATOR")),
        ("👓 リーダー", os.getenv("GPT_LEADER")),
        ("🐦 X投稿アシスタント", os.getenv("GPT_X_ASSIST")),
        ("📒 noteアシスタント", os.getenv("GPT_NOTE_ASSIST")),
    ],
    "AIと日本人シリーズ：": [
        ("✍️ 投稿文アシスタント", os.getenv("GPT_AIJP_POST")),
        ("🖼️ 画像アシスタント", os.getenv("GPT_AIJP_IMAGE")),
    ]
}

# GPTsリンクの表示
def render_gpt_links():
    st.subheader("🧠 GPTsリンク")

    for group_name, links in GPT_LINKS.items():
        st.markdown(f"**{group_name}**")

        cols = st.columns(6)

        for i, (name, url) in enumerate(links):

            with cols[i % 6]:
                st.link_button(
                    name,
                    url,
                    use_container_width=True
                )

# 画像保存用ディレクトリの作成
IMAGE_DIR = Path("images")
IMAGE_DIR.mkdir(exist_ok=True)

# セッションステートの初期化
for key in [
    "saved",
    "updated",
    "posted",
    "deleted",
    "edit_mode",
    "confirm_update",
    "confirm_delete",
]:
    if key not in st.session_state:
        st.session_state[key] = False

if "deleted_title" not in st.session_state:
    st.session_state["deleted_title"] = ""

# メモファイルのパス
MEMO_FILE = Path("data/post_memo.txt")
MEMO_FILE.parent.mkdir(exist_ok=True)

# メモの読み込み
def load_memo():
    if MEMO_FILE.exists():
        return MEMO_FILE.read_text(encoding="utf-8")
    return ""

# メモの保存
def save_memo(text):
    MEMO_FILE.write_text(text, encoding="utf-8")

# データベースから投稿データを取得
with psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                p.id,
                p.title,
                p.category,
                p.content,
                p.image_path,
                p.post_count,
                MAX(h.posted_at) AS last_posted
            FROM posts p
            LEFT JOIN post_history h
                ON p.id = h.post_id
            GROUP BY
                p.id,
                p.title,
                p.category,
                p.content,
                p.image_path,
                p.post_count
            ORDER BY p.id;
        """)
        rows = cur.fetchall()

# DataFrameに変換
df = pd.DataFrame(
    rows,
    columns=["ID", "タイトル", "カテゴリ", "本文", "画像パス", "投稿回数", "最終投稿日"]
)

# # ID非表示(必要に応じて)
# df = df.drop(columns=["ID"])

# 投稿件数計算
total_count = len(df)

unposted_count = len(
    df[df["投稿回数"] == 0]
)

posted_count = len(
    df[df["投稿回数"] > 0]
)

# 30日以上経過した再掲候補件数
repost_count = len(
    df[
        (df["投稿回数"] > 0)
        & (df["最終投稿日"].notna())
        & (
            df["最終投稿日"]
            <= pd.Timestamp.now() - pd.Timedelta(days=30)
        )
    ]
)

# タイトル表示
st.title("AIと日本人 投稿管理ツール")

#件数表示
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

with metric_col1:
    st.metric(f"**総投稿数**", total_count)

with metric_col2:
    st.metric(f"**未投稿**", unposted_count)

with metric_col3:
    st.metric(f"**投稿済み**", posted_count)

with metric_col4:
    st.metric(f"**再掲候補(30日以上経過)**", repost_count)

# カラム分割（2:1）
col1, col2 = st.columns([2, 1])

# 左カラム：投稿一覧の表示
with col1:
    st.subheader("📋 投稿一覧")

    # 絞り込みとソートのUIを横並びで表示
    filter_category_col, filter_status_col, filter_repost_col, filter_sort_col = st.columns(4)

    # カテゴリ絞り込みのUI
    with filter_category_col:
        categories = ["すべて"] + sorted(
            df["カテゴリ"].dropna().unique().tolist()
        )

        selected_category = st.selectbox(
            f"**カテゴリ**",
            categories
        )
    
    # 状態絞り込みのUI
    with filter_status_col:
        status_filter = st.selectbox(
            f"**状態**",
            [
                "すべて",
                "未投稿",
                "投稿済み"
            ]
        )
    
    # 再掲候補絞り込みのUI
    with filter_repost_col:
        repost_filter = st.selectbox(
            f"**再掲候補**",
            [
                "すべて",
                "10日以上経過",
                "30日以上経過",
                "60日以上経過"
            ]
        )
    
    # ソートオプションのUI
    with filter_sort_col:
        sort_option = st.selectbox(
            f"**ソート**",
            [
                "ID順",
                "投稿回数が少ない順",
                "投稿回数が多い順",
                "最終投稿日が古い順",
                "最終投稿日が新しい順"
            ]
        )

    # カテゴリ絞り込み処理
    if selected_category != "すべて":
        df = df[
            df["カテゴリ"] == selected_category
        ].reset_index(drop=True)

    # 状態絞り込み処理
    if status_filter == "未投稿":
        df = df[df["投稿回数"] == 0].reset_index(drop=True)

    elif status_filter == "投稿済み":
        df = df[df["投稿回数"] > 0].reset_index(drop=True)
    
    # 再掲候補絞り込み処理
    if repost_filter != "すべて":

        days_map = {
            "10日以上経過": 10,
            "30日以上経過": 30,
            "60日以上経過": 60
        }

        target_days = days_map[repost_filter]

        today = pd.Timestamp.now()

        df = df[
            (df["投稿回数"] > 0)
            & (df["最終投稿日"].notna())
            & (
                df["最終投稿日"]
                <= today - pd.Timedelta(days=target_days)
            )
        ].reset_index(drop=True)

    # ソート処理
    if sort_option == "投稿回数が少ない順":
        df = df.sort_values(
            by="投稿回数",
            ascending=True
        )

    elif sort_option == "投稿回数が多い順":
        df = df.sort_values(
            by="投稿回数",
            ascending=False
        )

    elif sort_option == "最終投稿日が古い順":
        df = df.sort_values(
            by="最終投稿日",
            ascending=True,
            na_position="first"
        )

    elif sort_option == "最終投稿日が新しい順":
        df = df.sort_values(
            by="最終投稿日",
            ascending=False,
            na_position="last"
        )

    else:
        df = df.sort_values(
            by="ID",
            ascending=True
        )

    df = df.reset_index(drop=True)

    # キーワード検索
    search_text = st.text_input(f"**キーワード検索**")

    if search_text:

        # 全角スペース→半角スペース
        search_text = search_text.replace("　", " ")

        # スペース区切りで分割
        keywords = search_text.split()

        # OR検索
        mask = False

        for keyword in keywords:
            keyword_mask = (
                df["タイトル"].str.contains(
                    keyword,
                    case=False,
                    na=False
                )
                |
                df["本文"].str.contains(
                    keyword,
                    case=False,
                    na=False
                )
            )

            mask = mask | keyword_mask

        df = df[mask].reset_index(drop=True)

    list_df = df[
        ["タイトル", "カテゴリ", "本文", "投稿回数", "最終投稿日"]
    ]

    event = st.dataframe(
        list_df,
        width="stretch",
        hide_index=True,
        height=1000,
        on_select="rerun",
        selection_mode="single-row"
    )

    # GPTsリンクの表示
    st.divider()
    render_gpt_links()

# 右カラム：投稿詳細の表示
with col2:
    st.subheader("📖 投稿詳細")

    selected = bool(event.selection.rows)

    if selected:
        selected_index = event.selection.rows[0]
        selected_row = df.iloc[selected_index]

        st.write(f"**タイトル：** {selected_row['タイトル']}")
        st.write(f"**カテゴリ：** {selected_row['カテゴリ']}")

        st.text_area(
            f"**本文：**",
            value=selected_row["本文"],
            height=300,
            key=f"content_{selected_row.name}"
        )

        tweet_text = selected_row["本文"]
        x_url = f"https://x.com/intent/post?text={quote(tweet_text)}"

        # components.html(
        #     f"""
        #     <button onclick='navigator.clipboard.writeText({json.dumps(tweet_text)})'>
        #         本文をコピー
        #     </button>
        #     """,
        #     height=40
        # )

        selected_post_id = selected_row["ID"]
        current_post_count = selected_row["投稿回数"]

        if current_post_count == 0:
            history_note = "X投稿済み"
        else:
            history_note = "X再掲済み"
        
        button_col1, button_col2 = st.columns(2)

        with button_col1:
            st.link_button("X投稿画面を開く", x_url)

        with button_col2:
            if st.button("投稿済みにする"):
                with psycopg.connect(
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT"),
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO post_history (
                                post_id,
                                note
                            )
                            VALUES (%s, %s);
                            """,
                            (
                                selected_post_id,
                                history_note
                            )
                        )

                        cur.execute(
                            """
                            UPDATE posts
                            SET post_count = post_count + 1
                            WHERE id = %s;
                            """,
                            (
                                selected_post_id,
                            )
                        )

                st.session_state["posted"] = True
                st.rerun()
        
        # 投稿情報・履歴の表示
        with st.expander("投稿情報・履歴"):

            # 画像パスの表示
            image_path = selected_row["画像パス"]

            if pd.isna(image_path) or image_path == "":
                st.write(f"**画像パス：** 未設定")
            else:
                st.write(f"**画像パス：** {image_path}")
                st.image(image_path)

            # 投稿回数の表示
            st.write(f"**投稿回数：** {selected_row['投稿回数']}")

            # 最終投稿日の表示
            last_posted = selected_row["最終投稿日"]

            if pd.isna(last_posted):
                st.write(f"**最終投稿日：** 未投稿")
            else:
                st.write(f"**最終投稿日：** {last_posted:%Y-%m-%d %H:%M}")
            
            # 投稿履歴の表示
            with psycopg.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            posted_at,
                            note
                        FROM post_history
                        WHERE post_id = %s
                        ORDER BY posted_at ASC;
                        """,
                        (
                            selected_post_id,
                        )
                    )
                    history_rows = cur.fetchall()

            st.write(f"**履歴：**")

            if history_rows:
                for posted_at, note in history_rows:
                    st.write(f"{posted_at:%Y-%m-%d %H:%M}：{note}")
            else:
                st.write("履歴なし")
        
        # 編集ボタンと削除ボタン
        edit_button_col, delete_button_col = st.columns(2)

        with edit_button_col:
            if st.button("編集する"):
                st.session_state["edit_mode"] = True
                st.session_state["confirm_update"] = False
                st.rerun()

        with delete_button_col:
            if st.button("削除する"):
                st.session_state["confirm_delete"] = True
                st.session_state["edit_mode"] = False
                st.session_state["confirm_update"] = False
                st.rerun()

        # 編集モードの処理        
        if st.session_state.get("edit_mode"):
            st.write("### 編集")

            # 編集フォーム
            edit_title = st.text_input(
                f"**タイトル編集：**",
                value=selected_row["タイトル"],
                key=f"edit_title_{selected_post_id}"
            )

            edit_category = st.selectbox(
                f"**カテゴリ編集：**",
                [
                    "4コマ投稿",
                    "AIと空気",
                    "日常観察"
                ],
                index=[
                    "4コマ投稿",
                    "AIと空気",
                    "日常観察"
                ].index(selected_row["カテゴリ"]),
                key=f"edit_category_{selected_post_id}"
            )

            edit_content = st.text_area(
                f"**本文編集：**",
                value=selected_row["本文"],
                height=300,
                key=f"edit_content_{selected_post_id}"
            )

            edit_col1, edit_col2 = st.columns(2)

            # 保存ボタン
            with edit_col1:
                if st.button("編集内容を保存"):
                    st.session_state["confirm_update"] = True
                    st.rerun()

            # キャンセルボタン
            with edit_col2:
                if st.button("編集をやめる"):
                    st.session_state["edit_mode"] = False
                    st.session_state["confirm_update"] = False
                    st.rerun()
            
            # 更新確認
            if st.session_state.get("confirm_update"):

                st.warning("この内容で更新しますか？")

                confirm_col1, confirm_col2 = st.columns(2)

                with confirm_col1:
                    if st.button("はい"):
                        with psycopg.connect(
                            host=os.getenv("DB_HOST"),
                            port=os.getenv("DB_PORT"),
                            dbname=os.getenv("DB_NAME"),
                            user=os.getenv("DB_USER"),
                            password=os.getenv("DB_PASSWORD"),
                        ) as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """
                                    UPDATE posts
                                    SET
                                        title = %s,
                                        category = %s,
                                        content = %s
                                    WHERE id = %s;
                                    """,
                                    (
                                        st.session_state[f"edit_title_{selected_post_id}"],
                                        st.session_state[f"edit_category_{selected_post_id}"],
                                        st.session_state[f"edit_content_{selected_post_id}"],
                                        selected_post_id
                                    )
                                )

                        st.session_state["updated"] = True
                        st.session_state["edit_mode"] = False
                        st.session_state["confirm_update"] = False
                        st.rerun()

                with confirm_col2:
                    if st.button("いいえ"):
                        st.session_state["confirm_update"] = False
                        st.rerun()

        # 削除処理
        if st.session_state.get("confirm_delete"):

            st.error("この投稿を削除しますか？")
            st.write(f"**タイトル：** {selected_row['タイトル']}")
            st.warning("この操作は元に戻せません")

            delete_yes_col, delete_no_col = st.columns(2)

            with delete_yes_col:
                if st.button("はい（削除する）"):

                    st.session_state["deleted_title"] = selected_row['タイトル']

                    with psycopg.connect(
                        host=os.getenv("DB_HOST"),
                        port=os.getenv("DB_PORT"),
                        dbname=os.getenv("DB_NAME"),
                        user=os.getenv("DB_USER"),
                        password=os.getenv("DB_PASSWORD"),
                    ) as conn:
                        with conn.cursor() as cur:

                            # 履歴削除
                            cur.execute(
                                """
                                DELETE FROM post_history
                                WHERE post_id = %s;
                                """,
                                (
                                    selected_post_id,
                                )
                            )

                            # 投稿削除
                            cur.execute(
                                """
                                DELETE FROM posts
                                WHERE id = %s;
                                """,
                                (
                                    selected_post_id,
                                )
                            )

                    st.session_state["deleted"] = True
                    st.session_state["confirm_delete"] = False
                    st.rerun()

            with delete_no_col:
                if st.button("いいえ"):
                    st.session_state["confirm_delete"] = False
                    st.rerun()

        # 更新完了メッセージ
        if st.session_state.get("updated"):
            st.info("投稿が更新されました")
            st.session_state["updated"] = False
        
        # 削除完了メッセージ
        if st.session_state.get("deleted"):
            st.info(f"「{st.session_state['deleted_title']}」を削除しました")
            st.session_state["deleted"] = False
            st.session_state["deleted_title"] = ""

    else:
        st.info("投稿詳細を確認するには一覧から選択してください")
    
        # 新規投稿フォーム
        st.subheader("✏️ 新規投稿")

        title = st.text_input(f"**タイトル：**")

        category = st.selectbox(
            f"**カテゴリ：**",
            [
                "4コマ投稿",
                "AIと空気",
                "日常観察"
            ]
        )

        content = st.text_area(
            f"**本文：**",
            height=300
        )

        uploaded_file = st.file_uploader(
            f"**画像ファイル：**",
            type=["png", "jpg", "jpeg", "webp"]
        )

        image_path = ""

        if uploaded_file is not None:
            image_path = uploaded_file.name
            st.write(f"**ファイルパス：** {image_path}")

        # 登録ボタンクリック後にSQLを更新し、画面の再実行を行う
        if st.button("登録"):
            with psycopg.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO posts (
                            title,
                            category,
                            content,
                            image_path
                        )
                        VALUES (%s, %s, %s, %s)
                        RETURNING id;
                        """,
                        (
                            title,
                            category,
                            content,
                            None
                        )
                    )

                    new_post_id = cur.fetchone()[0]

                    image_path = None

                    if uploaded_file is not None:
                        save_path = IMAGE_DIR / f"{new_post_id:06d}.jpg"

                        image = Image.open(uploaded_file)
                        image = image.convert("RGB")

                        image.save(
                            save_path,
                            "JPEG",
                            quality=95,
                            optimize=True
                        )

                        image_path = str(save_path)
                    
                    cur.execute(
                        """
                        UPDATE posts
                        SET image_path = %s
                        WHERE id = %s;
                        """,
                        (
                            image_path,
                            new_post_id
                        )
                    )

            st.session_state["saved"] = True
            st.rerun()

        if st.session_state.get("saved"):
            st.info("投稿が登録されました")
            st.session_state["saved"] = False
    
    # メモ機能
    st.subheader("📝 メモ")

    # 初回表示時だけファイルから読み込み
    if "memo_text" not in st.session_state:
        st.session_state.memo_text = load_memo()

    memo_text = st.text_area(
        "メモ書き",
        value=st.session_state.memo_text,
        height=600,
        key="memo_text"
    )

    if st.button("💾 メモを保存"):
        save_memo(st.session_state.memo_text)
        st.success("メモを保存しました")

