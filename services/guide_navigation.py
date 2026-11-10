"""Pure shared navigation: no Streamlit, activity data, provider SDK or legacy imports."""

def advance_step(index,total,direction):
    """Shared bounded guide navigation for programmes and institution onboarding."""
    delta={'next':1,'previous':-1}.get(direction,0)
    return max(0,min(index+delta,total-1))
