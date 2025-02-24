from db import db

class HDSTARtable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    ra = db.Column(db.Float, nullable=False)  # Decimal hours
    dec = db.Column(db.Float, nullable=False)  # Decimal degrees
    v_mag = db.Column(db.Float, nullable=False)
    
    # Additional columns
    dm = db.Column(db.String, nullable=True)
    deb1900 = db.Column(db.Float, nullable=True)
    rab1900 = db.Column(db.Float, nullable=True)
    q_ptm = db.Column(db.Float, nullable=True)
    n_ptm = db.Column(db.String, nullable=True)
    q_ptg = db.Column(db.Float, nullable=True)
    ptg = db.Column(db.Float, nullable=True)
    n_ptg = db.Column(db.String, nullable=True)
    spt = db.Column(db.String, nullable=True)
    int_field = db.Column(db.String, nullable=True)  # "int" is a reserved keyword, so we use "int_field"
    rem = db.Column(db.String, nullable=True)

class IndexTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    ra = db.Column(db.String, nullable=False)  # HMS format
    dec = db.Column(db.String, nullable=False)  # DMS format
    v_mag = db.Column(db.Float, nullable=False)
    
    # Additional columns
    const = db.Column(db.String, nullable=True)
    type = db.Column(db.String, nullable=True)
    maj_ax = db.Column(db.Float, nullable=True)
    min_ax = db.Column(db.Float, nullable=True)
    pos_ang = db.Column(db.Float, nullable=True)
    b_mag = db.Column(db.Float, nullable=True)
    j_mag = db.Column(db.Float, nullable=True)
    h_mag = db.Column(db.Float, nullable=True)
    k_mag = db.Column(db.Float, nullable=True)
    surf_br = db.Column(db.Float, nullable=True)
    hubble = db.Column(db.String, nullable=True)
    pax = db.Column(db.Float, nullable=True)
    pm_ra = db.Column(db.Float, nullable=True)
    pm_dec = db.Column(db.Float, nullable=True)
    rad_vel = db.Column(db.Float, nullable=True)
    redshift = db.Column(db.Float, nullable=True)
    cstar_u_mag = db.Column(db.Float, nullable=True)
    cstar_b_mag = db.Column(db.Float, nullable=True)
    cstar_v_mag = db.Column(db.Float, nullable=True)
    m = db.Column(db.Float, nullable=True)
    ngc = db.Column(db.String, nullable=True)
    ic = db.Column(db.String, nullable=True)
    cstar_names = db.Column(db.String, nullable=True)
    identifiers = db.Column(db.String, nullable=True)
    common_names = db.Column(db.String, nullable=True)
    ned_notes = db.Column(db.String, nullable=True)
    opengnc_notes = db.Column(db.String, nullable=True)
    sources = db.Column(db.String, nullable=True)

class NGCtable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    ra = db.Column(db.String, nullable=False)  # HMS format
    dec = db.Column(db.String, nullable=False)  # DMS format
    v_mag = db.Column(db.Float, nullable=False)
    
    # Additional columns
    const = db.Column(db.String, nullable=True)
    type = db.Column(db.String, nullable=True)
    maj_ax = db.Column(db.Float, nullable=True)
    min_ax = db.Column(db.Float, nullable=True)
    pos_ang = db.Column(db.Float, nullable=True)
    b_mag = db.Column(db.Float, nullable=True)
    j_mag = db.Column(db.Float, nullable=True)
    h_mag = db.Column(db.Float, nullable=True)
    k_mag = db.Column(db.Float, nullable=True)
    surf_br = db.Column(db.Float, nullable=True)
    hubble = db.Column(db.String, nullable=True)
    pax = db.Column(db.Float, nullable=True)
    pm_ra = db.Column(db.Float, nullable=True)
    pm_dec = db.Column(db.Float, nullable=True)
    rad_vel = db.Column(db.Float, nullable=True)
    redshift = db.Column(db.Float, nullable=True)
    cstar_u_mag = db.Column(db.Float, nullable=True)
    cstar_b_mag = db.Column(db.Float, nullable=True)
    cstar_v_mag = db.Column(db.Float, nullable=True)
    m = db.Column(db.Float, nullable=True)
    ngc = db.Column(db.String, nullable=True)
    ic = db.Column(db.String, nullable=True)
    cstar_names = db.Column(db.String, nullable=True)
    identifiers = db.Column(db.String, nullable=True)
    common_names = db.Column(db.String, nullable=True)
    ned_notes = db.Column(db.String, nullable=True)
    opengnc_notes = db.Column(db.String, nullable=True)
    sources = db.Column(db.String, nullable=True)
