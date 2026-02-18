# Troubleshooting

## Page Loads but Query Fails

- Verify `API_BASE_URL` is reachable from browser
- Verify DblpService `/api/health` returns `ok`
- Check browser console for CORS errors

## Query Always Returns Empty

- Ensure DblpService database build is completed
- Ensure author input format is valid (one per line)

## Runtime DB Issues

- Check permissions for `COAUTHORS_RUNTIME_DB`
- Check disk capacity
- Back up and recreate runtime DB when needed
