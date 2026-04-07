-- Wipe existing review data (clean slate)
DELETE FROM review_responses;
DELETE FROM review_requests;

-- Make department_id required on review_requests
ALTER TABLE review_requests MODIFY department_id INT NOT NULL;
