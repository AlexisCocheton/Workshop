# Enjeux NIS2 et DORA — PROJECT RESILIENCE-ALPHA

> Activité simulée : plateforme de paiement **fictive** → relève par analogie du secteur financier, donc de **DORA**, et des exigences de cybersécurité transverses de **NIS2**.
> Objet de ce document : situer honnêtement ce que notre démonstrateur **prouve réellement** au regard de ces textes, et ce qu'un prototype de 4 jours **ne peut pas** prouver, puis formuler des recommandations à une direction.
> Rappel : données 100 % fictives, aucune donnée bancaire réelle — ce travail est pédagogique.

---

## 1. Rappel bref des deux cadres

### NIS2 (directive UE 2022/2555)

Relève le niveau de cybersécurité des entités essentielles et importantes. Exigences structurantes :

- **Mesures de gestion des risques de sécurité des SI** (analyse de risques, politiques, durcissement, contrôle d'accès, chiffrement, gestion des secrets).
- **Gestion des incidents** : détection, traitement, journalisation.
- **Notification** des incidents significatifs aux autorités (CSIRT/ANSII) dans des délais courts (alerte précoce ~24 h, notification ~72 h).
- **Continuité d'activité** : sauvegarde, gestion de crise, reprise.
- **Responsabilité de la direction** (gouvernance, formation, redevabilité).

### DORA (règlement UE 2022/2554)

Résilience opérationnelle numérique du **secteur financier**. Piliers :

1. **Gestion des risques TIC** : cadre, identification des actifs, protection, détection.
2. **Gestion, classification et notification des incidents** liés aux TIC (incidents majeurs).
3. **Tests de résilience opérationnelle numérique** : tests réguliers, et tests avancés (TLPT) pour les plus exposés.
4. **Gestion du risque lié aux prestataires tiers de TIC** (contrats, registre, concentration).
5. **Partage d'informations** sur les cybermenaces.

Fil rouge commun aux deux textes : **savoir détecter, résister, se rétablir, tracer et rendre compte**.

---

## 2. Ce que notre démonstrateur démontre vs ce qu'il ne peut pas démontrer

Lecture de la colonne « Démontré ? » : ✅ démontré concrètement · ⚠️ partiellement/esquissé · ❌ hors de portée d'un prototype de 4 jours.

| Exigence | NIS2 / DORA | Démontré par notre démonstrateur ? | Commentaire concret |
|---|---|---|---|
| Analyse de risques TIC formalisée | NIS2 + DORA (P1) | ✅ | `ebios-rm.md` : EBIOS RM complet, biens supports réels, risques résiduels. |
| Protection / durcissement | NIS2 + DORA (P1) | ✅ | Conteneurs non-root, ports internes non exposés, images figées, WAF Caddy en frontal. |
| Gestion des secrets / chiffrement | NIS2 + DORA (P1) | ✅ | Secrets (JWT, Bearer) sous **SOPS**, hors du code ; auth JWT sur endpoints. |
| **Détection d'incident** | NIS2 + DORA (P2) | ✅ | Détecteur ML (LOF non supervisé) sur le taux de 5xx, sans seuil codé en dur. |
| **Journalisation / traçabilité** | NIS2 + DORA (P2, P3) | ✅ | Loki/Promtail (logs) + Prometheus/Grafana (métriques) ; incident et reprise tracés. |
| **Réponse / reprise après incident** | NIS2 (continuité) + DORA (P1/P2) | ✅ | Remédiation automatique (redémarrage `api`) + preuve par transaction réussie ; RTO/RPO dans `pca-pra.md`. |
| **Test de résilience** (chaos / attaque jouée) | DORA (P3) | ✅ | Attaque Red Team réelle depuis un PC distinct = test de résilience de bout en bout. |
| Test de résilience **avancé** (TLPT, périodicité) | DORA (P3) | ⚠️ | Un seul scénario joué une fois ; pas de programme de tests récurrents ni de pentest cadré. |
| Classification de la gravité d'un incident | NIS2 + DORA (P2) | ⚠️ | Gravité évaluée dans l'EBIOS, mais pas de procédure de classification outillée. |
| Gestion de crise / rôles formalisés | NIS2 (continuité) | ⚠️ | Rôles décrits dans `pca-pra.md`, mais pas d'organisation ni d'astreinte réelle. |
| **Notification aux autorités** (24 h/72 h) | NIS2 + DORA (P2) | ❌ | Aucun canal réel vers un CSIRT ; hors périmètre technique et organisationnel. |
| **Gouvernance d'entreprise / responsabilité de la direction** | NIS2 + DORA | ❌ | Pas d'entité, pas de politique validée par une direction. |
| **Gestion des prestataires tiers de TIC** (contrats, registre) | DORA (P4) | ❌ | Pas de fournisseurs réels ni de contrats ; registre inexistant. |
| Audits / certifications / conformité vérifiée | NIS2 + DORA | ❌ | Aucun audit indépendant possible sur un prototype de 4 jours. |
| Sauvegarde / restauration de la base | NIS2 (continuité) | ❌ | Non implémenté ; la remédiation ne couvre pas la corruption de `db` (cf. `pca-pra.md`). |
| Partage d'informations sur les menaces | DORA (P5) | ❌ | Hors périmètre. |

### Lecture d'ensemble

Le prototype est **fort sur l'axe technique de la résilience opérationnelle** — détecter, se rétablir, tracer, tester par une attaque réelle — qui est précisément le cœur de DORA (piliers 1, 2, 3). Il est **structurellement muet sur l'axe organisationnel et juridique** — notification, gouvernance, tiers, audits — qui suppose une entreprise, des processus et du temps, non une maquette de 4 jours. Cette honnêteté est un atout en soutenance : on ne confond pas « démontrer une capacité » et « être conforme ».

---

## 3. Recommandations à une direction

Argumentées, hiérarchisées, et fondées sur des **éléments vérifiables** issus du démonstrateur.

### R1 — Capitaliser sur la détection + reprise automatique, mais investir pour **corriger la cause**

Le démonstrateur prouve que l'on sait restaurer la disponibilité en ~30–60 s sans humain. Mais (RR1/RR2 de l'EBIOS) la reprise ne ferme pas la vulnérabilité `/pay/callback`. **Priorité 1 :** financer la correction des causes (auth du callback, rate-limiting, patch) en plus de l'automatisation. *Vérifiable sur :* logs Loki montrant une attaque rejouable après redémarrage.

### R2 — Traiter le trou de la **continuité des données** (RPO des données persistées)

La reprise ne couvre ni la corruption ni la perte de `db`. **Priorité 1 :** sauvegardes régulières + procédure de restauration testée. Sans cela, le RPO ≈ 0 annoncé ne vaut que pour l'indisponibilité, pas pour l'intégrité. *Vérifiable sur :* absence actuelle de mécanisme de sauvegarde dans l'architecture.

### R3 — Transformer l'attaque jouée en **programme de tests récurrents** (DORA P3)

Une attaque réussie une fois est une démonstration, pas un test de résilience au sens de DORA. **Priorité 2 :** rejouer le scénario à intervalle régulier (chaos/attaque), ajouter des scénarios (DoS persistant, injection), suivre la qualité du modèle ML (faux positifs/négatifs, RR4). *Vérifiable sur :* historique Prometheus/Grafana des exécutions.

### R4 — Mettre en place le volet **organisationnel** que le prototype ne peut pas porter

Notification aux autorités (24 h/72 h), classification des incidents, gouvernance et responsabilité de la direction, registre des prestataires TIC. **Priorité 2–3 :** ce sont des processus, pas du code ; ils doivent exister avant toute mise en production réelle. *Vérifiable sur :* la colonne ❌ du tableau §2.

### R5 — Fonder les décisions sur des **indicateurs mesurables**, pas sur des déclarations

Le démonstrateur fournit déjà des preuves objectives exploitables en pilotage : RTO réellement mesuré sur Grafana, taux de 5xx avant/après, journal de la remédiation dans Loki, score d'anomalie du modèle, requêtes bloquées en 403 par le WAF. **Priorité continue :** exiger que chaque exigence réglementaire soit adossée à un indicateur vérifiable plutôt qu'à une case cochée.

### Arbitrage recommandé

| Priorité | Investissement | Justification |
|---|---|---|
| **1** | Correction de la cause (R1) + sauvegarde/restauration `db` (R2) | Les deux angles morts que la reprise automatique laisse ouverts ; impact direct sur le risque résiduel. |
| **2** | Programme de tests récurrents (R3) + volet organisationnel/notification (R4) | Conformité DORA/NIS2 au-delà de la capacité technique. |
| **Continu** | Pilotage par indicateurs vérifiables (R5) | Transforme la démonstration en preuve de conformité auditable. |

**Conclusion :** le démonstrateur prouve une **capacité réelle de résilience opérationnelle** (détection, reprise, traçabilité, test par attaque), ce qui est l'esprit de DORA et de NIS2. Il n'établit pas la **conformité**, qui exige l'organisation, les processus de notification, la gestion des tiers et des audits — à construire au-delà du prototype. La valeur du projet pour une direction est précisément de **séparer ce qui est techniquement démontré de ce qui reste à décider et à financer**.
