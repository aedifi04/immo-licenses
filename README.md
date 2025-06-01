
# ImmoPro License Database

Ce dépôt contient la base de données publique des licences valides pour l'application ImmoPro.

## Format attendu :
Chaque entrée doit contenir :
- `email` : adresse mail liée à la licence
- `license_key` : clé d'activation
- `hwid` : identifiant matériel unique de l'utilisateur

## Exemple :
```json
{
  "email": "client@example.com",
  "license_key": "IMMO-XXXX-YYYY-ZZZZ",
  "hwid": "A1B2C3D4E5F6"
}
```

Ce fichier est utilisé par l'application pour vérifier la validité d'une activation.
