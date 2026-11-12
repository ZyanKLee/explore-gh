# Fixtures

Die Form aller Antworten wurde am 12.11.2026 gegen das echte GitHub geprüft.

- `search_repositories.json`: Antwort von `GET /search/repositories`. Von Hand
  geschrieben.
- `graphql_repo_*.json`: ein einzelner `Repository`-Knoten, so wie ihn die Abfrage des
  Adapters anfordert. Die Tests packen ihn in `{"data": {"r0": …}}`. Von Hand
  geschrieben, damit keine Namen und E-Mail-Adressen echter Personen im Repo landen.
- `star_history.json`: echte Antwort von `GET /repos/{owner}/{repo}/stargazers/history`
  (6 Wochen, neueste zuerst, `week` ist der Sonntag als Unix-Zeit, `days` beginnt am
  Sonntag).
