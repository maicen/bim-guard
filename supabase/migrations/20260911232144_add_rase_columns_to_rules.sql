-- Add nullable RASE tracking metadata to rules table
ALTER TABLE rules
    ADD COLUMN rase_requirement text,
    ADD COLUMN rase_applicability jsonb,
    ADD COLUMN rase_selection jsonb,
    ADD COLUMN rase_exception jsonb;
