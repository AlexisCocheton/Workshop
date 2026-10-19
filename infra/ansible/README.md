# Ansible

Automatise le déploiement de la plateforme sur le PC Hôte.

## Prérequis

```powershell
pip install ansible
ansible-galaxy collection install community.docker
```

## Déployer

```powershell
cd infra/ansible
ansible-playbook -i inventory.ini deploy.yml
```

Le playbook lance `docker compose up` sur l'hôte défini dans `inventory.ini`.
Pour un vrai PC Hôte distant, remplacer la ligne `localhost` par son adresse et
retirer `ansible_connection=local`.

## Place d'Ansible vs Docker Compose

- **Docker Compose** décrit les conteneurs et leurs liens (`compose.yml`).
- **Ansible** automatise l'opération de déploiement de façon reproductible et
  documentée, et pourrait orchestrer d'autres étapes (préparation de l'hôte,
  redéploiement après incident) sans action manuelle.
