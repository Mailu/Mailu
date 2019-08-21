-- name: create_mailu_user!
-- Create the mailu user if it does not exist.
do $$
begin
    create user mailu;
    exception when others then
    raise notice 'mailu user not created -- already exists';
end
$$;

-- name: create_health_user!
-- Create the mailu user if it does not exist.
do $$
begin
    create user health;
    exception when others then
    raise notice 'health user not created -- already exists';
end
$$;

-- name: grant_health!
-- Grant connect permission for the health user
grant connect
    on database postgres
    to health;

-- name: update_pw!
alter
    user mailu
    password :pw;

-- name: check_db
-- check if the mailu db exists
select 1
    from pg_database
    where datname = 'mailu';

-- name: create_db!
-- create the mailu db
create
    database mailu
    owner mailu;
