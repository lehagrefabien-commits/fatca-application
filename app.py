import os
import uuid
from datetime import datetime

from flask import Flask, render_template, request, send_file, abort, url_for
from docx import Document

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)

# =========================
# 1) Contexte (page d'accueil)
# =========================
CONTEXT = {
    "fr": (
        "<strong>Contexte – Accord FATCA</strong><br><br>"
        "Par un arrêt interlocutoire rendu fin 2025, la Cour des marchés a décidé de saisir "
        "la Cour de justice de l’Union européenne (CJUE) de treize questions préjudicielles "
        "relatives à la conformité de l’accord intergouvernemental FATCA avec le droit de l’Union européenne.<br><br>"
        "Cette saisine fait suite à la décision n°79/2025 du 24 avril 2025 de l’Autorité de protection "
        "des données (APD), par laquelle plusieurs violations du RGPD ont été constatées et une "
        "mise en conformité dans un délai d’un an a été ordonnée.<br><br>"
        "C’est dans ce contexte juridique désormais porté au niveau européen que la présente démarche "
        "permet aux personnes concernées d’exercer leurs droits."
    ),
    "nl": (
        "<strong>Context – FATCA-akkoord</strong><br><br>"
        "Bij een interlocutoir arrest eind 2025 heeft het Marktenhof beslist om dertien "
        "prejudiciële vragen voor te leggen aan het Hof van Justitie van de Europese Unie "
        "(HvJ-EU) over de verenigbaarheid van het FATCA-akkoord met het Unierecht.<br><br>"
        "Deze verwijzing volgt op beslissing nr. 79/2025 van 24 april 2025 van de "
        "Gegevensbeschermingsautoriteit (GBA), waarbij meerdere inbreuken op de AVG werden "
        "vastgesteld en een termijn van één jaar voor conformiteit werd opgelegd.<br><br>"
        "Tegen deze Europeesrechtelijke achtergrond stelt deze toepassing betrokken personen "
        "in staat hun rechten inzake gegevensbescherming uit te oefenen."
    ),
}

# =========================
# 2) Textes UI (formulaire & page merci)
# =========================
TEXTS = {
    "fr": {
        "title": "Générer une demande d’effacement FATCA",
        "subtitle": "Renseignez vos coordonnées pour générer un document Word prêt à imprimer et signer.",
        "civilite": "Civilité",
        "monsieur": "Monsieur",
        "madame": "Madame",
        "nom_prenom": "Nom et prénom",
        "adresse": "Adresse (rue, numéro)",
        "cp_ville": "Code postal – Ville",
        "lieu": "Lieu (ex. Bruxelles)",
        "date_naissance": "Date de naissance (JJ/MM/AAAA)",
        "generate": "Générer le document",
        "privacy": "Aucune donnée n’est conservée : les informations saisies servent uniquement à générer le document.",
        "ready_title": "Votre document est prêt",
        "ready_sub": "Téléchargez, imprimez et signez votre courrier avant de l’envoyer au SPF Finances.",
        "download": "Télécharger le document",
        "support_title": "Soutenir l’Association des Américains Accidentels (AAA)",
        "support_sub": "Si ce générateur vous a été utile, vous pouvez soutenir l’action de l’AAA via le formulaire ci-dessous.",
    },
    "nl": {
        "title": "FATCA-verwijderingsverzoek genereren",
        "subtitle": "Vul uw gegevens in om een Word-document te genereren dat u kunt afdrukken en ondertekenen.",
        "civilite": "Aanspreking",
        "monsieur": "Heer",
        "madame": "Mevrouw",
        "nom_prenom": "Naam en voornaam",
        "adresse": "Adres (straat, nummer)",
        "cp_ville": "Postcode – Gemeente",
        "lieu": "Plaats (bv. Brussel)",
        "date_naissance": "Geboortedatum (DD/MM/JJJJ)",
        "generate": "Document genereren",
        "privacy": "Er worden geen persoonsgegevens bewaard: de ingevoerde gegevens worden enkel gebruikt om het document te genereren.",
        "ready_title": "Uw document is klaar",
        "ready_sub": "Download, druk af en onderteken uw brief voordat u die naar de FOD Financiën verstuurt.",
        "download": "Document downloaden",
        "support_title": "Steun de Association des Américains Accidentels (AAA)",
        "support_sub": "Als deze tool nuttig was, kunt u de werking van AAA steunen via het formulier hieronder.",
    },
}


# =========================
# 3) Outils de remplacement Word
# =========================
def _replace_in_paragraph(paragraph, mapping: dict):
    # Reconstruit le texte complet du paragraphe à partir des runs,
    # puis remplace les balises et réinjecte le résultat.
    full_text = "".join(run.text for run in paragraph.runs)
    changed = False
    for k, v in mapping.items():
        if k in full_text:
            full_text = full_text.replace(k, v)
            changed = True

    if changed:
        if paragraph.runs:
            for run in paragraph.runs:
                run.text = ""
            paragraph.runs[0].text = full_text
        else:
            paragraph.add_run(full_text)


def _replace_in_doc(doc: Document, mapping: dict):
    # Paragraphes
    for p in doc.paragraphs:
        _replace_in_paragraph(p, mapping)

    # Tables (cellules)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_in_paragraph(p, mapping)


# =========================
# 4) Routes web
# =========================
@app.route("/", methods=["GET"])
def home():
    # Par défaut, on affiche le contexte en français.
    # L'utilisateur choisit ensuite FR/NL via les boutons.
    return render_template("langue.html", context_text=CONTEXT["fr"])


@app.route("/fr", methods=["GET"])
def form_fr():
    return _render_form("fr")


@app.route("/nl", methods=["GET"])
def form_nl():
    return _render_form("nl")


def _render_form(lang: str):
    if lang not in ("fr", "nl"):
        abort(404)

    # Valeur par défaut affichée (vous pouvez laisser vide si vous préférez)
    default_date = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        "form.html",
        lang=lang,
        t=TEXTS[lang],
        default_date=default_date,
    )


@app.route("/generate", methods=["POST"])
def generate():
    # 1) Langue
    lang = request.form.get("lang", "fr").strip()
    if lang not in ("fr", "nl"):
        lang = "fr"

    # 2) Champs de formulaire
    civilite = request.form.get("civilite", "H").strip()
    nom_prenom = request.form.get("nom_prenom", "").strip()
    adresse = request.form.get("adresse", "").strip()
    cp_ville = request.form.get("cp_ville", "").strip()
    lieu = request.form.get("lieu", "").strip()
    date_naissance = request.form.get("date_naissance", "").strip()

    # Vérification minimale
    if not all([nom_prenom, adresse, cp_ville, lieu, date_naissance]):
        abort(400, "Champs manquants. Merci de compléter tous les champs.")

    # 3) Choix du template Word selon la langue
    template_filename = "template_fr.docx" if lang == "fr" else "template_nl.docx"
    template_path = os.path.join(APP_DIR, "word_templates", template_filename)

    if not os.path.exists(template_path):
        abort(500, f"Template Word introuvable : word_templates/{template_filename}")

    # 4) Mapping des balises communes
    # Important: la balise {{DATE}} est utilisée dans les templates fournis.
    # Ici, on met la date du jour automatiquement.
    date_courrier = datetime.now().strftime("%d/%m/%Y")

    mapping = {
        "{{NOM_PRENOM}}": nom_prenom,
        "{{ADRESSE}}": adresse,
        "{{CP_VILLE}}": cp_ville,
        "{{LIEU}}": lieu,
        "{{DATE}}": date_courrier,
        "{{DATE_NAISSANCE}}": date_naissance,
    }

    # 5) Accords / formules selon langue et civilité
    if lang == "fr":
        if civilite == "F":
            mapping.update({
                "{{APPEL}}": "Madame, Monsieur",
                "{{SOUSSIGNE}}": "soussignée",
                "{{NE}}": "née",
                "{{RESIDENT_FISCAL}}": "résidente fiscale",
            })
        else:
            mapping.update({
                "{{APPEL}}": "Madame, Monsieur",
                "{{SOUSSIGNE}}": "soussigné",
                "{{NE}}": "né",
                "{{RESIDENT_FISCAL}}": "résident fiscal",
            })
    else:
        # Néerlandais: neutre (pas d'accord genré)
        mapping.update({
            "{{APPEL}}": "Geachte heer, mevrouw",
            "{{SOUSSIGNE}}": "ondergetekende",
            "{{NE}}": "geboren",
            "{{RESIDENT_FISCAL}}": "fiscaal inwoner",
        })

    # 6) Génération du document
    doc = Document(template_path)
    _replace_in_doc(doc, mapping)

    token = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"{token}.docx")
    doc.save(output_path)

    # 7) Page "merci" avec lien de téléchargement
    download_url = url_for("download", token=token)
    return render_template("merci.html", download_url=download_url, t=TEXTS[lang])


@app.route("/download/<token>", methods=["GET"])
def download(token: str):
    path = os.path.join(OUTPUT_DIR, f"{token}.docx")
    if not os.path.exists(path):
        abort(404)

    # Nom affiché au téléchargement
    return send_file(
        path,
        as_attachment=True,
        download_name="Demande_effacement_FATCA.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    # Utilisé uniquement si vous lancez en local (ce qui n'est pas nécessaire chez vous).
    app.run(host="127.0.0.1", port=5000, debug=True)
