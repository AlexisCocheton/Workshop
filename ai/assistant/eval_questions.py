"""Jeu de questions d'évaluation de la recherche du RAG.

Chaque question est une vraie question d'opérateur. `source` est le document de
`docs/` qui contient la réponse, et `must_contain` un terme qui DOIT apparaître
dans au moins un passage retrouvé (souvent un identifiant exact, l'angle mort du
vectoriel seul). On mesure si la recherche ramène le bon document et ce terme.

À tenir à jour quand on ajoute ou modifie un document de `docs/`.
"""

QUESTIONS = [
    {
        "question": "Que signifie l'état anomaly du détecteur ?",
        "source": "detection-anomalies.md",
        "must_contain": "anomaly",
    },
    {
        "question": "Que faire quand le détecteur affiche no_model ?",
        "source": "detection-anomalies.md",
        "must_contain": "no_model",
    },
    {
        "question": "Que veut dire err_5xx_rate élevé ?",
        "source": "detection-anomalies.md",
        "must_contain": "err_5xx_rate",
    },
    {
        "question": "Comment lire un z-score dans une alerte ?",
        "source": "detection-anomalies.md",
        "must_contain": "z-score",
    },
    {
        "question": "Comment vérifier que le service est vraiment rétabli après une reprise ?",
        "source": "reponse-incident.md",
        "must_contain": "transaction",
    },
    {
        "question": "Que faire si le détecteur signale la catégorie app_attack ?",
        "source": "reponse-incident.md",
        "must_contain": "app_attack",
    },
    {
        "question": "Comment réagir à un incident de catégorie service_error ?",
        "source": "reponse-incident.md",
        "must_contain": "service_error",
    },
    {
        "question": "Un redémarrage suffit-il à corriger une fuite de données ?",
        "source": "reponse-incident.md",
        "must_contain": "disponibilité",
    },
    {
        "question": "Qui décide de bloquer l'adresse IP d'un attaquant ?",
        "source": "reponse-incident.md",
        "must_contain": "WAF",
    },
    {
        "question": "Que faire quand l'API ne répond plus (api_down) ?",
        "source": "reponse-incident.md",
        "must_contain": "api_down",
    },
    {
        "question": "Par où passent toutes les requêtes de la plateforme ?",
        "source": "architecture.md",
        "must_contain": "WAF",
    },
    {
        "question": "Quel composant a le droit d'agir sur le système ?",
        "source": "architecture.md",
        "must_contain": "remédiation",
    },
    {
        "question": "Où regarder pour voir les blocages du WAF ?",
        "source": "architecture.md",
        "must_contain": "Grafana",
    },
    {
        "question": "Quel est le RTO visé pour le service de paiement ?",
        "source": "continuite-reprise.md",
        "must_contain": "RTO",
    },
    {
        "question": "Un redémarrage corrige-t-il une fuite de données ?",
        "source": "continuite-reprise.md",
        "must_contain": "disponibilité",
    },
    {
        "question": "Que faire si la reprise automatique ne fonctionne pas ?",
        "source": "continuite-reprise.md",
        "must_contain": "repli manuel",
    },
]
