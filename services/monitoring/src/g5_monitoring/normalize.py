"""De una muestra de /v1/metrics del platform-manager a hosts normalizados (unidades del placement).

RAM y disco en MB; CPU real en centésimas de CPU. Los compromisos (vCPU, RAM y disco usados) salen del registro
transaccional (reservas de G5 en Linux, Nova en OpenStack), no del consumo medido (HLD 4.7.5).
"""

GIB = 1024


def linux_hosts(rows, now):
    hosts = []
    for r in rows or []:
        cap, alloc, m = r.get("capacity") or {}, r.get("allocated") or {}, r.get("metrics")
        error = r.get("error")
        host = {
            "id": r["node"], "provider": "linux", "zone": r.get("zone") or "linux",
            "cpu_cores": (m or {}).get("cpu_cores") or cap.get("vcpus") or 1,
            "vcpus_max": cap.get("vcpus"),
            "ram_mb": int(cap.get("memory_mb", 0)), "disk_mb": int(cap.get("disk_gb", 0) * GIB),
            "vcpus_used": int(alloc.get("vcpus", 0)), "ram_used_mb": int(alloc.get("memory_mb", 0)),
            "disk_used_mb": int(alloc.get("disk_gb", 0) * GIB), "vms": int(alloc.get("vms", 0)),
            "occupied": int(alloc.get("vms", 0)) > 0,
            "cpu_real_cent": m.get("cpu_real_cent") if m else None,
            "memory_total_mb": m.get("memory_total_mb") if m else None,
            "memory_available_mb": m.get("memory_available_mb") if m else None,
            "disk_free_mb": m.get("disk_free_mb") if m else None,
            "load": m.get("load") if m else None,
            "vm_usage": m.get("vms", []) if m else [],
            "measured_at": m.get("timestamp") if m else None,
            "healthy": bool(r.get("enabled")) and m is not None and not error,
            "error": error or (None if r.get("enabled") else "en mantenimiento"),
        }
        host["age_s"] = round(max(0.0, now - host["measured_at"]), 1) if host["measured_at"] else None
        hosts.append(host)
    return hosts


def openstack_hosts(block, measured_at, now):
    hosts = []
    for r in (block or {}).get("hosts", []):
        local = int((r.get("local_gb") or 0) * GIB)
        # Compromiso como lo cuenta Nova (local_gb_used = suma de los flavors); es lo que su scheduler hace cumplir.
        # disk_available_least (peor caso si los qcow2 crecieran) solo se informa: en el clúster sale negativo con
        # 2 VMs y, si mandara, rechazaríamos slices que Nova acepta.
        used_disk = int((r.get("local_gb_used") or 0) * GIB)
        least = r.get("disk_available_least")
        up = r.get("state") == "up" and r.get("status") == "enabled"
        hosts.append({
            "id": r["node"], "provider": "openstack", "zone": r.get("zone") or "nova",
            "cpu_cores": r.get("vcpus") or 1, "vcpus_max": None,
            "ram_mb": int(r.get("memory_mb") or 0), "disk_mb": local,
            "vcpus_used": int(r.get("vcpus_used") or 0), "ram_used_mb": int(r.get("memory_mb_used") or 0),
            "disk_used_mb": max(0, used_disk), "vms": int(r.get("running_vms") or 0),
            "occupied": int(r.get("running_vms") or 0) > 0,
            # CPU real del compute: sin dato (es compartido y no hay acceso a los workers); el placement usa la
            # demanda completa. Sí hay uso medido de cada VM de G5 (diagnósticos de Nova) y la carga del compute.
            "cpu_real_cent": None,
            "memory_total_mb": None, "memory_available_mb": None,
            "disk_free_mb": None if least is None else int(least * GIB), "load": r.get("load"),
            "vm_usage": r.get("vm_usage") or [], "measured_at": measured_at,
            "age_s": round(max(0.0, now - measured_at), 1) if measured_at else None,
            "healthy": up, "error": None if up else "hipervisor %s/%s" % (r.get("state"), r.get("status")),
        })
    return hosts


def hosts_from_sample(sample, now):
    """Muestra completa -> {'linux': [...], 'openstack': [...]} con la antigüedad calculada a `now`."""
    os_block = sample.get("openstack")
    return {"linux": linux_hosts(sample.get("linux"), now),
            "openstack": openstack_hosts(os_block, sample.get("timestamp"), now) if os_block is not None else [],
            "openstack_error": (os_block or {}).get("error")}
